"""
Legge dal cloud Meross se il termostato sta chiamando la caldaia
e aggiorna la variabile Voice Monkey STATO_RISCALDAMENTO.

Secrets su GitHub:
  MEROSS_EMAIL, MEROSS_PASSWORD   credenziali dell'app Meross (MFA disattivata)
  VM_TOKEN                        token API di Voice Monkey
Opzionali:
  VM_VARIABILE   nome variabile (default STATO_RISCALDAMENTO)
  VALORE_ACCESO  valore quando la caldaia scalda (default 2)
  VALORE_SPENTO  valore quando la caldaia è ferma (default 0)
  MEROSS_REGION  iotx-eu / iotx-us / iotx-ap (default iotx-eu)
"""
import asyncio
import os
import sys

import requests
from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager

EMAIL = os.environ["MEROSS_EMAIL"]
PASSWORD = os.environ["MEROSS_PASSWORD"]
VM_TOKEN = os.environ["VM_TOKEN"]
VARIABILE = os.environ.get("VM_VARIABILE", "STATO_RISCALDAMENTO")
ACCESO = os.environ.get("VALORE_ACCESO", "2")
SPENTO = os.environ.get("VALORE_SPENTO", "0")
REGION = os.environ.get("MEROSS_REGION", "iotx-eu")

VM_URL = "https://api-v3.voicemonkey.io/variables"


async def leggi_stato_caldaia() -> bool:
    client = await MerossHttpClient.async_from_user_password(
        api_base_url=f"https://{REGION}.meross.com",
        email=EMAIL,
        password=PASSWORD,
    )
    manager = MerossManager(http_client=client)
    try:
        await manager.async_init()
        await manager.async_device_discovery()
        # Qualsiasi termostato Meross (mts200, mts215b, ...)
        termostati = [d for d in manager.find_devices()
                      if d.type.lower().startswith("mts") and hasattr(d, "get_thermostat_state")]
        if not termostati:
            tipi = [d.type for d in manager.find_devices()]
            raise RuntimeError(f"Nessun termostato trovato. Dispositivi sull'account: {tipi}")

        dev = termostati[0]
        await dev.async_update()
        stato = dev.get_thermostat_state()
        if stato is None:
            raise RuntimeError("Il termostato non ha restituito uno stato")
        grezzo = dict(stato._state)
        print(f"Termostato: {dev.name} ({dev.type})")
        print(f"Dati grezzi: {grezzo}")

        if "state" not in grezzo:
            raise RuntimeError("Il termostato non riporta il campo 'state': controlla i dati grezzi sopra")
        # 'state' = 1 -> il relè sta chiamando la caldaia, 2 -> fermo
        return grezzo.get("onoff", 1) == 1 and grezzo["state"] == 1
    finally:
        manager.close()
        await client.async_logout()


def aggiorna_voice_monkey(valore: str) -> None:
    r = requests.put(
        VM_URL,
        json={"token": VM_TOKEN, "variable": VARIABILE, "value": valore},
        timeout=20,
    )
    r.raise_for_status()
    print(f"Voice Monkey: {VARIABILE} = {valore}")


def main() -> int:
    scalda = asyncio.run(leggi_stato_caldaia())
    print("Caldaia:", "ACCESA" if scalda else "SPENTA")
    aggiorna_voice_monkey(ACCESO if scalda else SPENTO)
    return 0


if __name__ == "__main__":
    sys.exit(main())

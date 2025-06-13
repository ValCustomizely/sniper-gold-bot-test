import asyncio
import httpx
import os
import json
from datetime import datetime, timedelta
from notion_client import Client

# === MODE TEST ===
MODE_TEST = True

# === Initialisation dynamique des bases ===
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID_TEST" if MODE_TEST else "NOTION_DATABASE_ID"]
SEUILS_DATABASE_ID = os.environ["SEUILS_DATABASE_ID_TEST" if MODE_TEST else "SEUILS_DATABASE_ID"]
POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]

notion = Client(auth=NOTION_API_KEY)

if MODE_TEST:
    print(f"[BOOT] MODE TEST | {datetime.utcnow().isoformat()}", flush=True)
    print(f"[INFO] Signal DB : {NOTION_DATABASE_ID}", flush=True)
    print(f"[INFO] Seuils DB : {SEUILS_DATABASE_ID}", flush=True)

SEUILS_MANUELS = []
DERNIERE_MAJ_HORAIRES = set()
ETAT_PATH = "etat_cassure.json"

def charger_etat():
    if not os.path.exists(ETAT_PATH):
        return {"seuil": None, "compteur": 0}
    with open(ETAT_PATH, "r") as f:
        return json.load(f)

def sauvegarder_etat(seuil, compteur):
    with open(ETAT_PATH, "w") as f:
        json.dump({"seuil": seuil, "compteur": compteur}, f)

def get_last_trading_day():
    today = datetime.utcnow().date()
    weekday = today.weekday()
    if weekday == 0:
        return today - timedelta(days=3)
    elif weekday == 6:
        return today - timedelta(days=2)
    elif weekday == 5:
        return today - timedelta(days=1)
    else:
        return today - timedelta(days=1)

async def mettre_a_jour_seuils_auto():
    try:
        print("[INFO] Mise à jour automatique des seuils", flush=True)
        yesterday = get_last_trading_day().isoformat()
        today = datetime.utcnow().date().isoformat()
        url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/day/{yesterday}/{yesterday}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={
                "adjusted": "true",
                "sort": "desc",
                "limit": 1,
                "apiKey": POLYGON_API_KEY
            }, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                print("[WARN] Aucune donnée Polygon", flush=True)
                return

            candle = results[0]
            high, low, close = candle["h"], candle["l"], candle["c"]
            pivot = round((high + low + close) / 3, 2)
            r1 = round((2 * pivot) - low, 2)
            s1 = round((2 * pivot) - high, 2)
            r2 = round(pivot + (high - low), 2)
            s2 = round(pivot - (high - low), 2)
            r3 = round(high + 2 * (pivot - low), 2)
            s3 = round(low - 2 * (high - pivot), 2)

            seuils = [
                {"valeur": r3, "type": "résistance"},
                {"valeur": r2, "type": "résistance"},
                {"valeur": r1, "type": "résistance"},
                {"valeur": pivot, "type": "pivot"},
                {"valeur": s1, "type": "support"},
                {"valeur": s2, "type": "support"},
                {"valeur": s3, "type": "support"},
            ]

            for seuil in seuils:
                notion.pages.create(parent={"database_id": SEUILS_DATABASE_ID}, properties={
                    "Valeur": {"number": seuil["valeur"]},
                    "Type": {"select": {"name": seuil["type"]}},
                    "Date": {"date": {"start": today}}
                })
            print(f"[INFO] Seuils mis à jour pour {today}", flush=True)
    except Exception as e:
        print(f"[ERREUR] seuils auto : {e}", flush=True)

async def charger_seuils_depuis_notion():
    global SEUILS_MANUELS
    try:
        today = datetime.utcnow().date().isoformat()
        pages = notion.databases.query(database_id=SEUILS_DATABASE_ID, filter={"property": "Date", "date": {"equals": today}}).get("results", [])
        supports, resistances, pivots = [], [], []
        for page in pages:
            props = page["properties"]
            valeur = props.get("Valeur", {}).get("number")
            type_ = props.get("Type", {}).get("select", {}).get("name")
            if valeur is not None:
                if type_ == "support": supports.append(valeur)
                elif type_ == "résistance": resistances.append(valeur)
                elif type_ == "pivot": pivots.append(valeur)

        SEUILS_MANUELS = []
        for i, val in enumerate(sorted(resistances)): SEUILS_MANUELS.append({"valeur": val, "type": "résistance", "nom": f"R{i+1}"})
        for val in pivots: SEUILS_MANUELS.append({"valeur": val, "type": "pivot", "nom": "Pivot"})
        for i, val in enumerate(sorted(supports, reverse=True)): SEUILS_MANUELS.append({"valeur": val, "type": "support", "nom": f"S{i+1}"})
    except Exception as e:
        print(f"[ERREUR] chargement seuils : {e}", flush=True)

def calculer_tp(seuil_casse, pivot):
    if seuil_casse is None or pivot is None: return None
    return round(seuil_casse + (seuil_casse - pivot) * 0.8, 2)

def est_heure_de_mise_a_jour_solide():
    now = datetime.utcnow()
    return now.hour == 1 and f"{now.date().isoformat()}_1" not in DERNIERE_MAJ_HORAIRES and not DERNIERE_MAJ_HORAIRES.add(f"{now.date().isoformat()}_1")

async def fetch_gold_data():
    await charger_seuils_depuis_notion()
    etat = charger_etat()
    now = datetime.utcnow()
    today = now.date().isoformat()
    url = f"https://api.polygon.io/v2/aggs/ticker/C:XAUUSD/range/1/minute/{today}/{today}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params={"adjusted": "true", "sort": "desc", "limit": 1, "apiKey": POLYGON_API_KEY}, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                print("[ERREUR] Pas de donnée minute", flush=True)
                return

            candle = results[0]
            last_price = candle["c"]
            volume = candle["v"]
            pivot = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "Pivot"), None)

            seuil_prec = etat["seuil"]
            if seuil_prec:
                seuil_prec_val = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == seuil_prec), None)
                if seuil_prec_val:
                    if (seuil_prec.startswith("R") and last_price <= seuil_prec_val - 0.2) or (seuil_prec.startswith("S") and last_price >= seuil_prec_val + 0.2):
                        sauvegarder_etat(None, 0)
                        etat = {"seuil": None, "compteur": 0}

            cassures_resistances = [(s["valeur"], s["nom"]) for s in SEUILS_MANUELS if s["type"] == "résistance" and last_price > s["valeur"] + 0.5]
            cassures_supports = [(s["valeur"], s["nom"]) for s in SEUILS_MANUELS if s["type"] == "support" and last_price < s["valeur"] - 0.5]

            signal_type = None
            seuil_casse = None
            nom_seuil_casse = None

            if cassures_resistances:
                seuil_casse, nom_seuil_casse = max(cassures_resistances, key=lambda x: x[0])
                ecart = round(last_price - seuil_casse, 2)
                signal_type = f"📈 Cassure {nom_seuil_casse} +{ecart}$"
            elif cassures_supports:
                seuil_casse, nom_seuil_casse = min(cassures_supports, key=lambda x: x[0])
                ecart = round(seuil_casse - last_price, 2)
                signal_type = f"📉 Cassure {nom_seuil_casse} -{ecart}$"
            else:
                r1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "R1"), None)
                s1 = next((s["valeur"] for s in SEUILS_MANUELS if s["nom"] == "S1"), None)
                if pivot and r1 and pivot < last_price <= r1 + 0.5:
                    signal_type = f"🚧📈 -{round(r1 - last_price, 2)}$ du R1"
                elif pivot and s1 and s1 - 0.5 <= last_price < pivot:
                    signal_type = f"🚧📉 +{round(last_price - s1, 2)}$ du S1"

            if signal_type and seuil_casse:
                compteur = 1 if nom_seuil_casse != etat["seuil"] else etat["compteur"] + 1
                sauvegarder_etat(nom_seuil_casse, compteur)
                if compteur >= 5:
                    signal_type += " 🚧"

            if signal_type:
                props = {
                    "Signal": {"title": [{"text": {"content": signal_type}}]},
                    "Horodatage": {"date": {"start": now.isoformat()}},
                    "Prix": {"number": float(last_price)},
                    "Volume": {"number": int(volume)},
                    "Commentaire": {"rich_text": [{"text": {"content": "Signal via Polygon.io"}}]}
                }
                if seuil_casse:
                    props["SL"] = {"number": round(seuil_casse - 1, 2) if "📈" in signal_type else round(seuil_casse + 1, 2)}
                    props["SL suiveur"] = {"number": round(last_price + 5, 2) if "📈" in signal_type else round(last_price - 5, 2)}
                    props["TP"] = {"number": calculer_tp(seuil_casse, pivot)}

                notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=props)
                print(f"[INFO] {signal_type} | {last_price}$ | Vol: {volume}", flush=True)

        except Exception as e:
            print(f"[ERREUR] fetch_gold_data : {e}", flush=True)

async def main_loop():
    while True:
        if est_heure_de_mise_a_jour_solide():
            await mettre_a_jour_seuils_auto()
        await fetch_gold_data()
        await asyncio.sleep(60)

async def mise_en_route():
    await main_loop()

if __name__ == "__main__":
    print(f"[BOOT] {datetime.utcnow().isoformat()}", flush=True)
    try:
        asyncio.run(mise_en_route())
    except Exception as e:
        print(f"[ERREUR] critique bot : {e}", flush=True)

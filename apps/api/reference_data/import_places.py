"""Rebuild the bilingual launch catalog from a pinned India Post directory snapshot."""

import csv
import io
import re
from pathlib import Path
from urllib.request import urlopen

SOURCE = (
    "https://raw.githubusercontent.com/IndiaPost/pin/9903190eb2073826f869f0c384bb83a34a21ebd5/api/v01/csv"
)
AREAS = {
    "201001": {
        "Ghaziabad H.O": "गाज़ियाबाद",
        "Nehru Nagar S.O (Ghaziabad)": "नेहरू नगर",
        "Ashok Nagar S.O (Ghaziabad)": "अशोक नगर",
        "Ramte Ram Road S.O": "रामते राम रोड",
    },
    "201005": {"Sahibabad S.O": "साहिबाबाद", "Bhopura": "भोपुरा", "Pasonda B.O": "पसौंडा"},
    "201012": {"Vasundhra S.O": "वसुंधरा", "Kaushambi S.O": "कौशाम्बी"},
    "201204": {
        "Modi Nagar S.O": "मोदीनगर",
        "Niwari B.O": "निवाड़ी",
        "Patla B.O": "पतला",
        "Sikri Kalan B.O": "सीकरी कलाँ",
    },
    "201206": {"Murad Nagar S.O (Ghaziabad)": "मुरादनगर", "Duhai B.O": "दुहाई", "Abupur B.O": "अबूपुर"},
    "201102": {"Loni S.O": "लोनी", "Chirori B.O": "चिरोड़ी", "Mandola B.O": "मंडोला"},
    "201014": {"Makanpur B.O": "मकनपुर", "Shipra Sun City S.O": "शिप्रा सन सिटी"},
}


def main():
    output = []
    for pin, translations in AREAS.items():
        with urlopen(f"{SOURCE}/{pin}.csv", timeout=15) as response:
            records = {r["officename"]: r for r in csv.DictReader(io.StringIO(response.read().decode()))}
        for office, hi in translations.items():
            row = records[office]
            assert row["Districtname"] == "Ghaziabad" and row["pincode"] == pin
            name = re.sub(r" (?:H\.O|S\.O|B\.O)(?: \(Ghaziabad\))?$", "", office)
            slug = name.lower().replace(" ", "-")
            output.append([f"{pin}-{slug}", name, hi, pin])
    with Path(__file__).with_name("localities.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["id", "en", "hi", "pin"])
        writer.writerows(output)


if __name__ == "__main__":
    main()

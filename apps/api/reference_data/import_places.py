"""Rebuild the bilingual launch catalog from a pinned India Post directory snapshot."""
import csv
import io
from pathlib import Path
from urllib.request import urlopen

SOURCE = "https://raw.githubusercontent.com/IndiaPost/pin/9903190eb2073826f869f0c384bb83a34a21ebd5/api/v01/csv"
AREAS = {
    "301001": {"Alwar H.O": "अलवर", "Akbarpur B.O": "अकबरपुर", "Siliserh B.O": "सिलीसेढ़",
               "Delhi Gate Alwar S.O": "दिल्ली गेट अलवर", "Umren B.O": "उमरैण", "Chandoli B.O": "चंदोली"},
    "301022": {"Thanagazi S.O": "थानागाजी", "Kishori B.O": "किशोरी", "Suratgarh B.O": "सूरतगढ़"},
    "301406": {"Malakhera S.O": "मालाखेड़ा", "Jamalpur B.O": "जमालपुर", "Barkhera B.O": "बरखेड़ा"},
    "301035": {"Jatwara B.O": "जटवाड़ा", "Khoh B.O": "खोह"},
    "301408": {"Rajgarh (Alwar) S.O": "राजगढ़ (अलवर)", "Sakat B.O": "सकट", "Machari B.O": "माचाड़ी"},
}


def main():
    output = []
    for pin, translations in AREAS.items():
        with urlopen(f"{SOURCE}/{pin}.csv", timeout=15) as response:
            records = {r["officename"]: r for r in csv.DictReader(io.StringIO(response.read().decode()))}
        for office, hi in translations.items():
            row = records[office]
            assert row["Districtname"] == "Alwar" and row["pincode"] == pin
            name = office.rsplit(" ", 1)[0]
            slug = name.lower().replace(" (alwar)", "").replace(" ", "-")
            output.append([f"{pin}-{slug}", name, hi, pin])
    with Path(__file__).with_name("localities.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["id", "en", "hi", "pin"])
        writer.writerows(output)


if __name__ == "__main__":
    main()

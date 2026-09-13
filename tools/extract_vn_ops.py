"""Build Vietnam taxiway + callsign TSV from local AIP text cache (no download)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(
    r"F:\locdeptrai\PHAM TUAN LOC\Digital AIP VN\outputs\digital_aip_vn\aip_pdf_text_cache.json"
)

AIRPORTS = [
    ("VVNB", "HAN", "Noi Bai", "Nội Bài", "international"),
    ("VVTS", "SGN", "Tan Son Nhat", "Tân Sơn Nhất", "international"),
    ("VVDN", "DAD", "Da Nang", "Đà Nẵng", "international"),
    ("VVCR", "CXR", "Cam Ranh", "Cam Ranh", "international"),
    ("VVCT", "VCA", "Can Tho", "Cần Thơ", "international"),
    ("VVCI", "HPH", "Cat Bi", "Cát Bi", "international"),
    ("VVPQ", "PQC", "Phu Quoc", "Phú Quốc", "international"),
    ("VVPB", "HUI", "Phu Bai", "Phú Bài", "international"),
    ("VVVH", "VII", "Vinh", "Vinh", "international"),
    ("VVDL", "DLI", "Lien Khuong", "Liên Khương", "international"),
    ("VVBM", "BMV", "Buon Ma Thuot", "Buôn Ma Thuột", "domestic"),
    ("VVPC", "UIH", "Phu Cat", "Phù Cát", "domestic"),
    ("VVPK", "PXU", "Pleiku", "Pleiku", "domestic"),
    ("VVCA", "VCL", "Chu Lai", "Chu Lai", "domestic"),
    ("VVDH", "VDH", "Dong Hoi", "Đồng Hới", "domestic"),
    ("VVTH", "TBB", "Tuy Hoa", "Tuy Hòa", "domestic"),
    ("VVTX", "THD", "Tho Xuan", "Thọ Xuân", "domestic"),
    ("VVDB", "DIN", "Dien Bien", "Điện Biên", "domestic"),
    ("VVCM", "CAH", "Ca Mau", "Cà Mau", "domestic"),
    ("VVRG", "VKG", "Rach Gia", "Rạch Giá", "domestic"),
    ("VVCS", "VCS", "Con Dao", "Côn Đảo", "domestic"),
    ("VVNS", "SQH", "Na San", "Nà Sản", "domestic"),
]

# Vân Đồn is the 23rd civil AD (not ACV); keep because it is in regular service.
EXTRA = [("VVVD", "VDO", "Van Don", "Vân Đồn", "international")]

STARTS = {
    "VVBM": 639, "VVCA": 771, "VVCI": 853, "VVCM": 969, "VVCR": 1021, "VVCS": 1147,
    "VVCT": 1223, "VVDB": 1317, "VVDH": 1373, "VVDL": 1467, "VVDN": 1555, "VVNB": 1705,
    "VVPB": 2005, "VVPC": 2095, "VVPK": 2177, "VVPQ": 2273, "VVRG": 2379, "VVTH": 2465,
    "VVTS": 2531, "VVTX": 2787, "VVVD": 2873, "VVVH": 2965,
}
SPAN = {"VVTS": 8, "VVNB": 6, "VVDN": 5, "VVCR": 5, "VVPQ": 4}

SUPPLEMENT = {
    "VVTS": ["Z", "Z1", "Z6", "Z7"],
    "VVCR": ["E1", "E3", "E5", "E7"],
    "VVPB": ["W2", "W4", "E2", "SP"],
}

PHONETIC = {
    "A": "Alfa", "B": "Bravo", "C": "Charlie", "D": "Delta", "E": "Echo", "F": "Foxtrot",
    "G": "Golf", "H": "Hotel", "I": "India", "J": "Juliett", "K": "Kilo", "L": "Lima",
    "M": "Mike", "N": "November", "O": "Oscar", "P": "Papa", "Q": "Quebec", "R": "Romeo",
    "S": "Sierra", "T": "Tango", "U": "Uniform", "V": "Victor", "W": "Whiskey", "X": "X-ray",
    "Y": "Yankee", "Z": "Zulu",
}

ROLE_VI = {
    "N": "đường lăn chính phía Bắc",
    "S": "đường lăn song song / phía Nam",
    "E": "đường lăn song song / phía Đông",
    "W": "đường lăn song song / phía Tây",
    "P": "đường lăn nối (giữa đường CHC)",
    "V": "đường lăn sân đỗ / vào sân",
    "G": "đường lăn nối / rapid exit",
    "Z": "đường lăn trong sân đỗ",
    "Y": "đường lăn nối",
    "A": "đường lăn nối / vào sân",
    "B": "đường lăn song song / nhánh B",
    "SP": "đường lăn song song",
}

SKIP = {
    "RWY", "AD", "PCR", "NIL", "FM", "CL", "THR", "TDZ", "TWY", "APN", "CAT",
    "THE", "AND", "FOR", "NOT", "USE", "M", "U", "T", "X",
}

TWY_EN = re.compile(r"\bTWY\s+([A-Z]{1,3}\d{0,2})\b")
TWY_VI = re.compile(r"Đường lăn(?: song song| nối)?\s+([A-Z]{1,3}\d{0,2}|SP)\b")


def spoken(designator: str) -> str:
    if designator == "SP":
        return "Sierra Papa"
    m = re.fullmatch(r"([A-Z]{1,3})(\d{0,2})", designator)
    if not m:
        return designator
    letters, digits = m.group(1), m.group(2)
    parts = [PHONETIC.get(ch, ch) for ch in letters]
    if digits:
        parts.append(" ".join({"1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
                               "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine", "0": "Zero"}[d]
                              for d in digits))
    return " ".join(parts)


def parse_designators(text: str) -> list[str]:
    found = TWY_EN.findall(text) + TWY_VI.findall(text)
    out, seen = [], set()
    for raw in found:
        dsg = raw.upper()
        if dsg in SKIP or len(dsg) > 4:
            continue
        if dsg not in seen:
            seen.add(dsg)
            out.append(dsg)
    return out


def detail_map(text: str) -> dict[str, str]:
    details: dict[str, str] = {}
    for m in re.finditer(
        r"(?:Đường lăn(?: song song| nối)?|TWY)\s+([A-Z]{1,3}\d{0,2}|SP)\s*[:,]?\s*([^\n]{0,220})",
        text,
    ):
        dsg = m.group(1).upper()
        rest = re.sub(r"\s+", " ", m.group(2)).strip(" .;,-")
        rest = re.split(r"\s+[–-]\s+(?:Đường lăn|TWY)\b", rest, maxsplit=1)[0]
        if dsg not in details and rest:
            details[dsg] = rest[:160]
    return details


def tsv_row(domain, abbr, en, vi, note, source):
    cells = [domain, abbr, en, vi, note, source]
    if any("\t" in c or "\n" in c for c in cells):
        raise ValueError(cells)
    return "\t".join(cells)


def write_taxiways(pages: list[dict]) -> int:
    lines = ["domain\tabbr\ten\tvi\tnote\tsource"]
    n = 0
    for icao, iata, en_name, vi_name, kind in AIRPORTS + EXTRA:
        start = STARTS.get(icao)
        if start is None:
            lines.append(tsv_row(
                "taxiway", icao,
                f"{en_name} ({icao}/{iata}) taxiways",
                f"Đường lăn {vi_name} ({icao}/{iata})",
                "AIP Việt Nam — Nà Sản tạm dừng khai thác. Kiểm tra AIP/NOTAM khi mở lại. AIRAC 02/26.",
                "aipvn",
            ))
            n += 1
            continue
        span = SPAN.get(icao, 4)
        text = "\n".join((pages[j].get("text") or "") for j in range(start, min(start + span, len(pages))))
        designators = parse_designators(text)
        for extra in SUPPLEMENT.get(icao, []):
            if extra not in designators:
                designators.append(extra)
        if not designators:
            designators = ["MAIN"]
        details = detail_map(text)
        listed = ", ".join(d if d != "MAIN" else "(không ký hiệu riêng)" for d in designators)
        lines.append(tsv_row(
            "taxiway", icao,
            f"{en_name} taxiways: {listed}",
            f"Đường lăn {vi_name}: {listed}",
            f"AIP Việt Nam AD 2.{icao} §2.8, AIRAC 02/26 (hiệu lực 2026-05-14). IATA {iata}. "
            f"{'CHKQT' if kind=='international' else 'CHK nội địa'}. Không thay AIP khi có xung đột.",
            "aipvn",
        ))
        n += 1
        for dsg in designators:
            label = "TWY" if dsg == "MAIN" else f"TWY {dsg}"
            vi_label = "đường lăn (không ký hiệu riêng)" if dsg == "MAIN" else f"đường lăn {dsg}"
            letter = re.match(r"[A-Z]+", dsg)
            role = ROLE_VI.get(dsg, ROLE_VI.get(letter.group(0) if letter else "", "đường lăn"))
            speak = "taxiway" if dsg == "MAIN" else spoken(dsg)
            det = details.get(dsg, "")
            note = f"AIP AD 2.{icao} §2.8. {vi_name} ({icao}/{iata}). {role}. Đọc: {speak}."
            if det:
                note += " " + det
            lines.append(tsv_row(
                "taxiway",
                "" if dsg == "MAIN" else dsg,
                f"{label} ({icao})",
                f"{vi_label} — {vi_name}",
                note,
                "aipvn",
            ))
            n += 1
    (ROOT / "data" / "vn-taxiways.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return n


CALLSIGNS = [
    # ICAO, IATA, telephony, airline EN, airline VI, note
    ("HVN", "VN", "VIET NAM AIRLINES", "Vietnam Airlines", "Vietnam Airlines", "Hãng quốc gia. Đọc: Viet Nam Airlines + số hiệu."),
    ("VJC", "VJ", "VIETJETAIR", "Vietjet Air", "Vietjet Air", "Một số tài liệu ghi VIETJET. Đọc: Vietjet Air + số hiệu."),
    ("BAV", "QH", "BAMBOO", "Bamboo Airways", "Bamboo Airways", "Đọc: Bamboo + số hiệu."),
    ("PIC", "BL", "PACIFIC AIRLINES", "Pacific Airlines", "Pacific Airlines", "Trước đây Jetstar Pacific. Số hiệu hay codeshare VN6xxx. Đọc: Pacific Airlines."),
    ("VAG", "VU", "VIETRAVEL AIR", "Vietravel Airlines", "Vietravel Airlines", "Đọc: Vietravel Air + số hiệu."),
    ("VFC", "0V", "VASCO AIR", "VASCO", "VASCO (Vietnam Air Services Company)", "Hãng vùng, thuộc Vietnam Airlines. Đọc: Vasco Air."),
    ("SPQ", "9G", "SUN LUX", "Sun PhuQuoc Airways", "Sun PhuQuoc Airways", "Hãng giải trí/Phú Quốc. ICAO SPQ. Đọc: Sun Lux."),
    ("VSM", "", "VIETSTAR", "Vietstar Airlines", "Vietstar Airlines", "Charter / AOC. Đọc: Vietstar."),
    ("HAI", "HA", "HAI AU", "Hai Au Aviation", "Hải Âu Aviation", "Charter / thủy phi cơ (lịch sử)."),
    ("SAV", "", "SUN AIR", "Sun Air", "Sun Air", "Thuộc Sun Group."),
    ("BSF", "", "BLUE LIGHT", "Blue Sky Airways", "Blue Sky Airways", "Charter."),
    ("TTG", "", "VIETNAM CARGO", "Trai Thien Air Cargo", "Trải Thiên Air Cargo", "Hàng hóa."),
    ("KAL", "KE", "KOREAN AIR", "Korean Air", "Korean Air", "Thường xuyên HAN/SGN. Cargo + pax."),
    ("AAR", "OZ", "ASIANA", "Asiana Airlines", "Asiana Airlines", "Hàn Quốc."),
    ("JJA", "7C", "JEJU AIR", "Jeju Air", "Jeju Air", "Hàn Quốc LCC."),
    ("JNA", "LJ", "JIN AIR", "Jin Air", "Jin Air", "Hàn Quốc LCC."),
    ("TWB", "TW", "TEEWAY", "T'way Air", "T'way Air", "Hàn Quốc. Telephony TEEWAY."),
    ("ABL", "BX", "AIR BUSAN", "Air Busan", "Air Busan", "Hàn Quốc."),
    ("ESR", "ZE", "EASTARJET", "Eastar Jet", "Eastar Jet", "Hàn Quốc."),
    ("CSN", "CZ", "CHINA SOUTHERN", "China Southern", "China Southern Airlines", "Trung Quốc."),
    ("CES", "MU", "CHINA EASTERN", "China Eastern", "China Eastern Airlines", "Trung Quốc."),
    ("CCA", "CA", "AIR CHINA", "Air China", "Air China", "Trung Quốc."),
    ("CXA", "MF", "XIAMEN AIR", "Xiamen Airlines", "Xiamen Airlines", "Trung Quốc."),
    ("CSZ", "ZH", "SHENZHEN AIR", "Shenzhen Airlines", "Shenzhen Airlines", "Trung Quốc."),
    ("CSC", "3U", "SICHUAN", "Sichuan Airlines", "Sichuan Airlines", "Trung Quốc."),
    ("CQH", "9C", "AIR SPRING", "Spring Airlines", "Spring Airlines", "Trung Quốc LCC."),
    ("DKH", "HO", "AIR JUNEYAO", "Juneyao Airlines", "Juneyao Airlines", "Trung Quốc."),
    ("CAL", "CI", "DYNASTY", "China Airlines", "China Airlines (Đài Loan)", "Telephony DYNASTY."),
    ("EVA", "BR", "EVA", "EVA Air", "EVA Air", "Đài Loan."),
    ("SJX", "JX", "STARWALKER", "STARLUX Airlines", "STARLUX Airlines", "Đài Loan. Telephony STARWALKER."),
    ("CPA", "CX", "CATHAY", "Cathay Pacific", "Cathay Pacific", "Hồng Kông."),
    ("CRK", "HX", "BAUHINIA", "Hong Kong Airlines", "Hong Kong Airlines", "Telephony BAUHINIA."),
    ("HKE", "UO", "HONGKONG SHUTTLE", "HK Express", "HK Express", "LCC Hồng Kông."),
    ("SIA", "SQ", "SINGAPORE", "Singapore Airlines", "Singapore Airlines", ""),
    ("TGW", "TR", "SCOOTER", "Scoot", "Scoot", "LCC Singapore. Telephony SCOOTER."),
    ("THA", "TG", "THAI", "Thai Airways", "Thai Airways", ""),
    ("AIQ", "FD", "THAI ASIA", "Thai AirAsia", "Thai AirAsia", ""),
    ("TVJ", "VZ", "THAIVIET JET", "Thai Vietjet Air", "Thai Vietjet Air", "Liên danh Vietjet."),
    ("AXM", "AK", "ASIAN EXPRESS", "AirAsia", "AirAsia (Malaysia)", "Một số tài liệu ghi XANADU cho AirAsia X."),
    ("MAS", "MH", "MALAYSIAN", "Malaysia Airlines", "Malaysia Airlines", ""),
    ("BTK", "ID", "BATIK", "Batik Air", "Batik Air", "Indonesia."),
    ("GIA", "GA", "INDONESIA", "Garuda Indonesia", "Garuda Indonesia", ""),
    ("PAL", "PR", "PHILIPPINE", "Philippine Airlines", "Philippine Airlines", ""),
    ("CEB", "5J", "CEBU", "Cebu Pacific", "Cebu Pacific", "Cũng nghe BLUE JAY."),
    ("QTR", "QR", "QATARI", "Qatar Airways", "Qatar Airways", "Pax + cargo."),
    ("UAE", "EK", "EMIRATES", "Emirates", "Emirates", ""),
    ("ETD", "EY", "ETIHAD", "Etihad Airways", "Etihad Airways", ""),
    ("THY", "TK", "TURKISH", "Turkish Airlines", "Turkish Airlines", ""),
    ("AFL", "SU", "AEROFLOT", "Aeroflot", "Aeroflot", "Theo mùa / tình trạng khai thác."),
    ("AFR", "AF", "AIRFRANS", "Air France", "Air France", "Telephony AIRFRANS."),
    ("ANA", "NH", "ALL NIPPON", "ANA", "All Nippon Airways", ""),
    ("JAL", "JL", "JAPAN AIR", "Japan Airlines", "Japan Airlines", ""),
    ("AIC", "AI", "AIRINDIA", "Air India", "Air India", ""),
    ("IGO", "6E", "IFLY", "IndiGo", "IndiGo", "Telephony IFLY."),
    ("FIN", "AY", "FINNAIR", "Finnair", "Finnair", "Theo mùa."),
    ("BKP", "PG", "BANGKOK AIR", "Bangkok Airways", "Bangkok Airways", ""),
    ("LLA", "QV", "LAO", "Lao Airlines", "Lao Airlines", ""),
    ("KHV", "K6", "CAMBODIA", "Air Cambodia", "Air Cambodia", "Tên/telephony có thể đổi theo AOC."),
    ("FDX", "FX", "FEDEX", "FedEx", "FedEx", "Hàng hóa."),
    ("UPS", "5X", "UPS", "UPS", "UPS", "Hàng hóa."),
    ("CLX", "CV", "CARGOLUX", "Cargolux", "Cargolux", "Hàng hóa."),
    ("CSS", "O3", "SHUN FENG", "SF Airlines", "SF Airlines", "Hàng hóa Trung Quốc."),
    ("CKK", "CK", "CARGO KING", "China Cargo Airlines", "China Cargo Airlines", "Hàng hóa."),
    ("CAO", "CA", "AIRCHINA FREIGHT", "Air China Cargo", "Air China Cargo", "Hàng hóa."),
    ("YZR", "Y8", "YANGTZE RIVER", "Suparna Airlines", "Suparna Airlines", "Hàng hóa / Yangtze River."),
    ("GTI", "5Y", "GIANT", "Atlas Air", "Atlas Air", "Hàng hóa / ACMI."),
    ("CKS", "K4", "CONNIE", "Kalitta Air", "Kalitta Air", "Hàng hóa."),
]


def write_callsigns() -> int:
    lines = ["domain\tabbr\ten\tvi\tnote\tsource"]
    n = 0
    for icao, iata, tel, en_name, vi_name, extra in CALLSIGNS:
        iata_bit = f"IATA {iata}. " if iata else ""
        note = (
            f"ICAO {icao}. {iata_bit}Telephony / callsign: {tel}. "
            f"Hãng thường xuyên hoặc theo mùa tại Việt Nam. {extra} "
            "Đối chiếu Doc 8585 / AIP GEN 2.4 khi có xung đột."
        )
        lines.append(tsv_row(
            "callsign", icao, tel, vi_name,
            note, "icao8585",
        ))
        n += 1
        lines.append(tsv_row(
            "callsign", iata or icao, en_name, f"{vi_name} (hãng)",
            f"Tên hãng. Callsign vô tuyến: {tel}. ICAO {icao}. {iata_bit}{extra}",
            "icao8585",
        ))
        n += 1
    (ROOT / "data" / "vn-callsigns.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return n


def main() -> None:
    if not CACHE.is_file():
        raise SystemExit("Missing AIP text cache: %s" % CACHE)
    pages = json.loads(CACHE.read_text(encoding="utf-8"))["pages"]
    twy = write_taxiways(pages)
    cs = write_callsigns()
    print({"taxiway_rows": twy, "callsign_rows": cs})


if __name__ == "__main__":
    main()

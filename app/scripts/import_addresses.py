import argparse
import asyncio
import json
import math
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import insert, select, text

from app.core.database import get_engine, get_session_factory
from app.model import Address


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILE = PROJECT_ROOT / "data" / "ALS-GeoJSON.zip"
BATCH_SIZE = 1000


def clean(value) -> str:
    """将字段转换成干净的字符串，保留数字 0。"""
    return "" if value is None else str(value).strip()


def join_parts(parts, separator: str) -> str:
    return separator.join(
        value for part in parts if (value := clean(part))
    )


def building_number(data: dict) -> str:
    start = clean(data.get("BuildingNoFrom"))
    end = clean(data.get("BuildingNoTo"))

    if start and end and start != end:
        return f"{start}-{end}"

    return start or end


def format_address(data: dict, prefix: str) -> str:
    """拼接楼宇级地址，不导入楼层和单位。"""
    chinese = prefix == "Chi"

    street = data.get(f"{prefix}Street") or {}
    village = data.get(f"{prefix}Village") or {}
    estate = data.get(f"{prefix}Estate") or {}
    phase = estate.get(f"{prefix}Phase") or {}
    block = data.get(f"{prefix}Block") or {}

    street_number = building_number(street)
    village_number = building_number(village)

    block_no = clean(block.get("BlockNo"))
    block_descriptor = clean(block.get("BlockDescriptor"))

    phase_name = clean(phase.get("PhaseName"))
    if not phase_name:
        phase_no = clean(phase.get("PhaseNo"))
        if phase_no:
            phase_name = (
                f"第{phase_no}期"
                if chinese
                else f"PHASE {phase_no}"
            )

    if chinese:
        street_text = join_parts(
            [
                street.get("LocationName"),
                street.get("StreetName"),
                f"{street_number}號" if street_number else "",
            ],
            "",
        )
        village_text = join_parts(
            [
                village.get("LocationName"),
                village.get("VillageName"),
                f"{village_number}號" if village_number else "",
            ],
            "",
        )
        block_text = join_parts([block_no, block_descriptor], "")

        return join_parts(
            [
                data.get("Region"),
                data.get("ChiDistrict"),
                street_text,
                village_text,
                estate.get("EstateName"),
                phase_name,
                data.get("BuildingName"),
                block_text,
            ],
            "",
        )

    street_text = join_parts(
        [
            street_number,
            street.get("StreetName"),
            street.get("LocationName"),
        ],
        " ",
    )
    village_text = join_parts(
        [
            village_number,
            village.get("VillageName"),
            village.get("LocationName"),
        ],
        " ",
    )

    if block.get("BlockDescriptorPrecedenceIndicator") == "N":
        block_text = join_parts([block_no, block_descriptor], " ")
    else:
        block_text = join_parts([block_descriptor, block_no], " ")

    region = {
        "HK": "HONG KONG",
        "KLN": "KOWLOON",
        "NT": "NEW TERRITORIES",
    }.get(data.get("Region"), data.get("Region"))

    return join_parts(
        [
            block_text,
            data.get("BuildingName"),
            phase_name,
            estate.get("EstateName"),
            street_text,
            village_text,
            data.get("EngDistrict"),
            region,
        ],
        ", ",
    )

def read_coordinates(
    feature: dict,
) -> tuple[float | None, float | None]:
    geometry = feature.get("geometry")

    # 缺少位置时，保留地址，两个坐标都存为 NULL。
    if geometry is None:
        return None, None

    if geometry.get("type") != "Point":
        raise ValueError("坐标类型不是 Point")

    coordinates = geometry.get("coordinates")

    if coordinates is None or coordinates == []:
        return None, None

    if (
        not isinstance(coordinates, (list, tuple))
        or len(coordinates) < 2
    ):
        raise ValueError("坐标格式不完整")

    if coordinates[0] is None and coordinates[1] is None:
        return None, None

    # GeoJSON 顺序：经度、纬度。
    longitude = float(coordinates[0])
    latitude = float(coordinates[1])

    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        raise ValueError("经纬度超出范围")

    return longitude, latitude


def convert_feature(feature: dict) -> dict:
    premises = feature["properties"]["Address"]["PremisesAddress"]

    chinese = premises["ChiPremisesAddress"]
    english = premises["EngPremisesAddress"]

    longitude, latitude = read_coordinates(feature)

    address_zh = format_address(chinese, "Chi")
    address_en = format_address(english, "Eng")

    if not address_zh or not address_en:
        raise ValueError("中英文地址不能为空")

    return {
        "geo_address": clean(premises.get("GeoAddress")) or None,
        "building_name_zh": clean(chinese.get("BuildingName")) or None,
        "building_name_en": clean(english.get("BuildingName")) or None,
        "address_zh": address_zh,
        "address_en": address_en,
        "district_zh": clean(chinese.get("ChiDistrict")) or None,
        "district_en": clean(english.get("EngDistrict")) or None,
        "latitude": latitude,
        "longitude": longitude,
    }


def iter_addresses(zip_path: Path):
    skipped_no_coordinates = 0
    with ZipFile(zip_path) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if name.lower().endswith(".geojson")
            and "_3d_" not in name.lower()
        )

        if not names:
            raise ValueError("ZIP 中没有找到分区 GeoJSON 文件")

        for name in names:
            print(f"读取：{name}")

            # 每次只加载一个分区文件，不加载整个 ZIP 的内容。
            with archive.open(name) as file:
                document = json.loads(
                    file.read().decode("utf-8-sig")
                )

            if (
                document.get("type") != "FeatureCollection"
                or not isinstance(document.get("features"), list)
            ):
                raise ValueError(f"{name} 不是有效的 FeatureCollection")

            for index, feature in enumerate(
                document["features"],
                start=1,
            ):
                try:
                    row = convert_feature(feature)

                    if (
                        row["latitude"] is None
                        or row["longitude"] is None
                    ):
                        skipped_no_coordinates += 1
                        print(
                            f"跳过缺少坐标的地址："
                            f"{row['address_zh']}"
                        )
                        continue

                    yield row

                except (KeyError, TypeError, ValueError, IndexError) as exc:
                    raise ValueError(
                        f"{name} 第 {index} 条记录转换失败"
                    ) from exc

    print(f"缺少坐标，已跳过：{skipped_no_coordinates} 条")


def address_key(row: dict) -> tuple:
    """不能只按 geo_address 去重，同一位置可能有多个文字地址。"""
    return (
        row["geo_address"],
        row["address_zh"],
        row["address_en"],
    )


def preview(zip_path: Path) -> None:
    count = 0

    for row in iter_addresses(zip_path):
        count += 1

        if count <= 3:
            print(json.dumps(row, ensure_ascii=False, indent=2))

    print(f"\n预览完成：成功转换 {count} 条原始记录。")
    print("没有连接数据库，也没有写入数据。")


async def import_addresses(zip_path: Path) -> None:
    inserted = 0
    skipped = 0
    batch = []

    try:
        async with get_session_factory().begin() as session:
            # 防止两个导入脚本同时执行时重复插入。
            # 普通 SELECT 查询仍可以执行。
            await session.execute(
                text("LOCK TABLE addresses IN SHARE ROW EXCLUSIVE MODE")
            )

            result = await session.execute(
                select(
                    Address.geo_address,
                    Address.address_zh,
                    Address.address_en,
                )
            )

            seen = {tuple(row) for row in result.all()}

            for row in iter_addresses(zip_path):
                key = address_key(row)

                if key in seen:
                    skipped += 1
                    continue

                seen.add(key)
                batch.append(row)

                if len(batch) >= BATCH_SIZE:
                    await session.execute(insert(Address), batch)
                    inserted += len(batch)
                    batch.clear()

                    print(f"已处理新增 {inserted} 条，尚未提交")

            if batch:
                await session.execute(insert(Address), batch)
                inserted += len(batch)

        # 离开 begin() 后才完成事务提交。
        print("\n导入成功，事务已提交。")
        print(f"新增：{inserted}")
        print(f"跳过重复：{skipped}")

    finally:
        await get_engine().dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入香港 ALS 地址")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help="ALS ZIP 文件路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只转换和预览，不写数据库",
    )
    args = parser.parse_args()

    if not args.file.is_file():
        parser.error(f"找不到文件：{args.file}")

    if args.dry_run:
        preview(args.file)
    else:
        asyncio.run(import_addresses(args.file))


if __name__ == "__main__":
    main()
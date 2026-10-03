import json
import urllib.parse
import urllib.request

import mysql.connector

from config_api import KOBIS_API_KEY
from config_db import DB_CONFIG

# 영화사목록 조회 API
KOBIS_COMPANY_LIST_URL = (
    "https://kobis.or.kr/kobisopenapi/webservice/rest/company/searchCompanyList.json"
)

def fetch_kobis_company_list(cur_page=1, item_per_page=100):
    """
    KOBIS API에서 영화사목록을 가져옵니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "curPage": cur_page,
        "itemPerPage": item_per_page,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_COMPANY_LIST_URL}?{query_string}"

    print(f"KOBIS 영화사목록 API 요청 URL: {request_url}")

    try:
        with urllib.request.urlopen(request_url) as response:
            response_body = response.read().decode("utf-8")

        data = json.loads(response_body)

        return data.get("companyListResult", {})

    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return {}


def create_table_if_not_exists(connection):
    """
    영화사목록 데이터를 저장할 테이블을 생성합니다.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS kobis_company (
        company_cd VARCHAR(20) PRIMARY KEY,
        company_nm VARCHAR(255),
        company_nm_en VARCHAR(255),
        company_part_names VARCHAR(255),
        ceo_nm VARCHAR(255),
        filmo_names TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()


def truncate_table(connection):
    """
    실행 전에 영화사목록 테이블 데이터를 초기화합니다.
    """
    sql = "TRUNCATE TABLE kobis_company"

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()
    print("kobis_company 테이블 초기화 완료")


def save_companies_to_db(connection, company_list):
    """
    영화사목록 데이터를 DB에 저장합니다.
    """
    if not company_list:
        print("저장할 영화사 데이터가 없습니다.")
        return

    sql = """
    INSERT INTO kobis_company (
        company_cd,
        company_nm,
        company_nm_en,
        company_part_names,
        ceo_nm,
        filmo_names
    ) VALUES (
        %(company_cd)s,
        %(company_nm)s,
        %(company_nm_en)s,
        %(company_part_names)s,
        %(ceo_nm)s,
        %(filmo_names)s
    )
    ON DUPLICATE KEY UPDATE
        company_nm = VALUES(company_nm),
        company_nm_en = VALUES(company_nm_en),
        company_part_names = VALUES(company_part_names),
        ceo_nm = VALUES(ceo_nm),
        filmo_names = VALUES(filmo_names),
        updated_at = CURRENT_TIMESTAMP;
    """

    rows = []

    for item in company_list:
        row = {
            "company_cd": item.get("companyCd"),
            "company_nm": item.get("companyNm"),
            "company_nm_en": item.get("companyNmEn"),
            "company_part_names": item.get("companyPartNames"),
            "ceo_nm": item.get("ceoNm"),
            "filmo_names": item.get("filmoNames"),
        }

        if row["company_cd"]:
            rows.append(row)

    if not rows:
        print("저장할 영화사 데이터가 없습니다.")
        return

    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)

    connection.commit()

    print(f"{len(rows)}건의 영화사 정보 저장/업데이트 완료")


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_table_if_not_exists(connection)
        truncate_table(connection)

        for page in range(1, 1000):
            print(f"\n{page}페이지 조회 중...")

            result = fetch_kobis_company_list(
                cur_page=page,
                item_per_page=100,
            )

            company_list = result.get("companyList", [])

            if company_list:
                save_companies_to_db(connection, company_list)
            else:
                print("더 이상 데이터가 없습니다.")
                break

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")

    finally:
        connection.close()

    print("\n모든 작업 완료")


if __name__ == "__main__":
    main()



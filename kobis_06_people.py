import json
import math
import time
import urllib.parse
import urllib.request

import mysql.connector

# ==============================
# KOBIS API 설정
# ==============================
KOBIS_API_KEY = "07967092cdf290d53659a8dc6b23d5da"

# 영화인목록 조회 API
KOBIS_PEOPLE_LIST_URL = (
    "https://kobis.or.kr/kobisopenapi/webservice/rest/people/searchPeopleList.json"
)

# ==============================
# DB 접속 정보
# ==============================
DB_CONFIG = {
    "host": "localhost",
    "port": 3308,
    "database": "shop_db",
    "user": "shop_user007",
    "password": "dy",
    "charset": "utf8mb4",
}


def fetch_kobis_people_list(cur_page=1, item_per_page=100, max_retries=3):
    """
    KOBIS API에서 영화인목록을 가져옵니다.
    네트워크 오류 또는 일시적 장애 시 재시도합니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "curPage": cur_page,
        "itemPerPage": item_per_page,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_PEOPLE_LIST_URL}?{query_string}"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                request_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8")

            data = json.loads(response_body)
            return data.get("peopleListResult", {})

        except Exception as e:
            print(f"API 요청 중 오류 발생 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1)
            else:
                return {}

    return {}


def create_table_if_not_exists(connection):
    """
    영화인목록 데이터를 저장할 테이블을 생성합니다.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS kobis_people (
        people_cd VARCHAR(20) PRIMARY KEY COMMENT '영화인 코드',
        people_nm VARCHAR(255) COMMENT '영화인명',
        people_nm_en VARCHAR(255) COMMENT '영화인명(영문)',
        rep_role_nm VARCHAR(100) COMMENT '분야',
        filmo_names TEXT COMMENT '필모리스트',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='영화인목록';
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()
    print("kobis_people 테이블 확인 및 생성 완료")


def truncate_table(connection):
    """
    실행 전에 영화인목록 테이블 데이터를 초기화합니다.
    """
    sql = "TRUNCATE TABLE kobis_people"

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()
    print("kobis_people 테이블 초기화 완료")


def save_people_to_db(connection, people_list):
    """
    영화인목록 데이터를 DB에 저장합니다.
    """
    if not people_list:
        print("저장할 영화인 데이터가 없습니다.")
        return 0

    sql = """
    INSERT INTO kobis_people (
        people_cd,
        people_nm,
        people_nm_en,
        rep_role_nm,
        filmo_names
    ) VALUES (
        %(people_cd)s,
        %(people_nm)s,
        %(people_nm_en)s,
        %(rep_role_nm)s,
        %(filmo_names)s
    )
    ON DUPLICATE KEY UPDATE
        people_nm = VALUES(people_nm),
        people_nm_en = VALUES(people_nm_en),
        rep_role_nm = VALUES(rep_role_nm),
        filmo_names = VALUES(filmo_names),
        updated_at = CURRENT_TIMESTAMP;
    """

    rows = []

    for item in people_list:
        people_cd = item.get("peopleCd")
        if not people_cd:
            continue

        row = {
            "people_cd": people_cd,
            "people_nm": item.get("peopleNm"),
            "people_nm_en": item.get("peopleNmEn"),
            "rep_role_nm": item.get("repRoleNm"),
            "filmo_names": item.get("filmoNames"),
        }
        rows.append(row)

    if not rows:
        print("저장할 영화인 데이터가 없습니다.")
        return 0

    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)
        row_count = cursor.rowcount

    connection.commit()
    print(f"{len(rows)}건의 영화인 정보 저장/업데이트 완료 (DB 반영: {row_count}건)")
    return len(rows)


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_table_if_not_exists(connection)
        truncate_table(connection)

        item_per_page = 100
        total_saved_count = 0

        # 1페이지 조회 및 전체 개수(totCnt) 확인
        print("\n1페이지 조회 중...")
        result = fetch_kobis_people_list(cur_page=1, item_per_page=item_per_page)
        tot_cnt = int(result.get("totCnt", 0))
        people_list = result.get("peopleList", [])

        if people_list:
            saved_count = save_people_to_db(connection, people_list)
            total_saved_count += saved_count

        total_pages = math.ceil(tot_cnt / item_per_page) if item_per_page else 1
        print(f"\n전체 영화인 수: {tot_cnt}명, 총 페이지 수: {total_pages}페이지")
        print(f"누적 저장 데이터 수: {total_saved_count}/{tot_cnt}건")

        # 2페이지부터 순차 조회 및 저장
        for page in range(2, total_pages + 1):
            print(f"\n{page}/{total_pages}페이지 조회 중...")
            result = fetch_kobis_people_list(cur_page=page, item_per_page=item_per_page)
            if not result:
                print(f"{page}페이지 데이터를 가져오지 못했습니다. 다음 페이지로 진행합니다.")
                continue

            people_list = result.get("peopleList", [])

            if people_list:
                saved_count = save_people_to_db(connection, people_list)
                total_saved_count += saved_count
                print(f"누적 저장 데이터 수: {total_saved_count}/{tot_cnt}건")
            else:
                print("더 이상 데이터가 없습니다.")
                break

        print(f"\n총 {total_saved_count}건의 영화인 정보 처리 완료")

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")

    finally:
        connection.close()

    print("\n모든 작업 완료")


if __name__ == "__main__":
    main()

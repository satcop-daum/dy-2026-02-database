import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import mysql.connector

from config_api import KOBIS_API_KEY
from config_db import DB_CONFIG

# 영화인 상세정보 API
KOBIS_PEOPLE_INFO_URL = (
    "https://kobis.or.kr/kobisopenapi/webservice/rest/people/searchPeopleInfo.json"
)

def fetch_kobis_people_detail(people_cd, max_retries=3):
    """
    KOBIS API에서 특정 영화인의 상세정보를 조회합니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "peopleCd": people_cd,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_PEOPLE_INFO_URL}?{query_string}"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                request_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8")

            data = json.loads(response_body)
            return data.get("peopleInfoResult", {}).get("peopleInfo", {})

        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5 * attempt)
            else:
                print(f"[{people_cd}] 상세정보 API 조회 실패: {e}")
                return {}

    return {}


def create_detail_tables_if_not_exists(connection):
    """
    영화인 상세정보 및 영화인 필모그래피를 저장할 테이블들을 생성합니다.
    """
    with connection.cursor() as cursor:
        # 1. 영화인 상세정보 마스터 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kobis_people_detail (
            people_cd VARCHAR(20) PRIMARY KEY COMMENT '영화인 코드',
            people_nm VARCHAR(255) COMMENT '영화인명',
            people_nm_en VARCHAR(255) COMMENT '영화인명(영문)',
            sex VARCHAR(20) COMMENT '성별',
            rep_role_nm VARCHAR(100) COMMENT '영화인 분류명',
            homepages TEXT COMMENT '관련 URL',
            filmo_count INT DEFAULT 0 COMMENT '필모그래피 개수',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='영화인 상세정보';
        """)

        # 2. 영화인 필모그래피(참여 영화 목록) 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kobis_people_filmo (
            id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '고유 식별자',
            people_cd VARCHAR(20) NOT NULL COMMENT '영화인 코드',
            movie_cd VARCHAR(20) NOT NULL COMMENT '참여 영화코드',
            movie_nm VARCHAR(500) COMMENT '참여 영화명',
            movie_part_nm VARCHAR(100) NOT NULL DEFAULT '' COMMENT '참여분야',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
            UNIQUE KEY uk_people_movie_part (people_cd, movie_cd, movie_part_nm),
            KEY idx_movie_cd (movie_cd),
            KEY idx_people_cd (people_cd)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='영화인 필모그래피';
        """)

    connection.commit()
    print("영화인 상세정보 테이블(kobis_people_detail, kobis_people_filmo) 확인 및 생성 완료")


def get_target_people_codes(connection, limit=None):
    """
    kobis_people 테이블에서 조회 대상 영화인 코드 목록을 가져옵니다.
    """
    sql = "SELECT people_cd FROM kobis_people ORDER BY people_cd"
    if limit:
        sql += f" LIMIT {limit}"

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    return [row[0] for row in rows]


def save_people_details_batch(connection, details_list):
    """
    상세정보 배치 목록을 DB에 일괄 저장합니다.
    """
    if not details_list:
        return

    people_detail_sql = """
    INSERT INTO kobis_people_detail (
        people_cd, people_nm, people_nm_en, sex, rep_role_nm, homepages, filmo_count
    ) VALUES (
        %(people_cd)s, %(people_nm)s, %(people_nm_en)s, %(sex)s, %(rep_role_nm)s, %(homepages)s, %(filmo_count)s
    )
    ON DUPLICATE KEY UPDATE
        people_nm = VALUES(people_nm),
        people_nm_en = VALUES(people_nm_en),
        sex = VALUES(sex),
        rep_role_nm = VALUES(rep_role_nm),
        homepages = VALUES(homepages),
        filmo_count = VALUES(filmo_count),
        updated_at = CURRENT_TIMESTAMP;
    """

    filmo_sql = """
    INSERT INTO kobis_people_filmo (
        people_cd, movie_cd, movie_nm, movie_part_nm
    ) VALUES (
        %(people_cd)s, %(movie_cd)s, %(movie_nm)s, %(movie_part_nm)s
    )
    ON DUPLICATE KEY UPDATE
        movie_nm = VALUES(movie_nm),
        movie_part_nm = VALUES(movie_part_nm),
        updated_at = CURRENT_TIMESTAMP;
    """

    detail_rows = []
    filmo_rows = []

    for item in details_list:
        if not item or not item.get("peopleCd"):
            continue

        people_cd = item.get("peopleCd")
        people_nm = item.get("peopleNm")
        people_nm_en = item.get("peopleNmEn")
        sex = item.get("sex")
        rep_role_nm = item.get("repRoleNm")
        homepages = item.get("homepages", [])
        filmos = item.get("filmos", [])

        # homepages 처리 (리스트 내 항목이 문자열이거나 딕셔너리일 경우 대비)
        homepage_list = []
        for h in homepages:
            if isinstance(h, dict):
                hp = h.get("homepage") or h.get("url") or str(h)
                homepage_list.append(hp)
            elif isinstance(h, str):
                homepage_list.append(h)
        homepages_str = ", ".join(homepage_list) if homepage_list else None

        detail_rows.append({
            "people_cd": people_cd,
            "people_nm": people_nm,
            "people_nm_en": people_nm_en,
            "sex": sex,
            "rep_role_nm": rep_role_nm,
            "homepages": homepages_str,
            "filmo_count": len(filmos),
        })

        for f in filmos:
            movie_cd = f.get("movieCd")
            movie_nm = f.get("movieNm")
            movie_part_nm = f.get("moviePartNm") or ""
            if movie_cd:
                filmo_rows.append({
                    "people_cd": people_cd,
                    "movie_cd": movie_cd,
                    "movie_nm": movie_nm,
                    "movie_part_nm": movie_part_nm,
                })

    with connection.cursor() as cursor:
        if detail_rows:
            cursor.executemany(people_detail_sql, detail_rows)
        if filmo_rows:
            cursor.executemany(filmo_sql, filmo_rows)

    connection.commit()


def process_people_details(connection, people_codes, batch_size=50, max_workers=10):
    """
    영화인 목록을 멀티스레드로 조회하여 배치 단위로 DB에 저장합니다.
    """
    total = len(people_codes)
    print(f"총 {total}건의 영화인 상세정보 수집 시작 (동시 스레드: {max_workers})")

    completed = 0
    start_time = time.time()

    for i in range(0, total, batch_size):
        chunk = people_codes[i:i + batch_size]
        details_list = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(fetch_kobis_people_detail, code): code for code in chunk
            }

            for future in as_completed(future_to_code):
                try:
                    detail = future.result()
                    if detail:
                        details_list.append(detail)
                except Exception as exc:
                    code = future_to_code[future]
                    print(f"영화인 [{code}] 처리 중 예외 발생: {exc}")

        if details_list:
            save_people_details_batch(connection, details_list)

        completed += len(chunk)
        elapsed = time.time() - start_time
        print(f"진행 상황: {completed}/{total} ({completed / total * 100:.1f}%) 완료 - 소요 시간: {elapsed:.1f}초")


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_detail_tables_if_not_exists(connection)

        people_codes = get_target_people_codes(connection)
        if not people_codes:
            print("kobis_people 테이블에 조회할 영화인 데이터가 없습니다.")
            return

        process_people_details(connection, people_codes, batch_size=50, max_workers=10)

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")

    finally:
        connection.close()

    print("\n영화인 상세정보 수집 및 저장 완료")


if __name__ == "__main__":
    main()

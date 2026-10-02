import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import mysql.connector

# ==============================
# KOBIS API 설정
# ==============================
KOBIS_API_KEY = "07967092cdf290d53659a8dc6b23d5da"

# 영화사 상세정보 API
KOBIS_COMPANY_INFO_URL = (
    "https://kobis.or.kr/kobisopenapi/webservice/rest/company/searchCompanyInfo.json"
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


def fetch_kobis_company_detail(company_cd, max_retries=3):
    """
    KOBIS API에서 특정 영화사의 상세정보를 조회합니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "companyCd": company_cd,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_COMPANY_INFO_URL}?{query_string}"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                request_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8")

            data = json.loads(response_body)
            return data.get("companyInfoResult", {}).get("companyInfo", {})

        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5 * attempt)
            else:
                print(f"[{company_cd}] 상세정보 API 조회 실패: {e}")
                return {}

    return {}


def create_detail_tables_if_not_exists(connection):
    """
    영화사 상세정보, 영화사 분류, 영화사 필모그래피를 저장할 테이블들을 생성합니다.
    """
    with connection.cursor() as cursor:
        # 1. 영화사 상세정보 마스터 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kobis_company_detail (
            company_cd VARCHAR(20) PRIMARY KEY,
            company_nm VARCHAR(500),
            company_nm_en VARCHAR(500),
            ceo_nm VARCHAR(255),
            parts TEXT,
            filmo_count INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 2. 영화사 참여 분야(분류) 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kobis_company_part (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            company_cd VARCHAR(20) NOT NULL,
            company_part_nm VARCHAR(100) NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_comp_part (company_cd, company_part_nm)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 3. 영화사 필모그래피(참여 영화 목록) 테이블
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kobis_company_filmo (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            company_cd VARCHAR(20) NOT NULL,
            movie_cd VARCHAR(20) NOT NULL,
            movie_nm VARCHAR(500),
            company_part_nm VARCHAR(100) NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_comp_movie_part (company_cd, movie_cd, company_part_nm),
            KEY idx_movie_cd (movie_cd),
            KEY idx_company_cd (company_cd)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

    connection.commit()
    print("영화사 상세정보 테이블(kobis_company_detail, kobis_company_part, kobis_company_filmo) 확인 및 생성 완료")


def get_target_company_codes(connection, limit=None):
    """
    kobis_company 테이블에서 조회 대상 영화사 코드 목록을 가져옵니다.
    """
    sql = "SELECT company_cd FROM kobis_company ORDER BY company_cd"
    if limit:
        sql += f" LIMIT {limit}"

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    return [row[0] for row in rows]


def save_company_details_batch(connection, details_list):
    """
    상세정보 배치 목록을 DB에 일괄 저장합니다.
    """
    if not details_list:
        return

    company_detail_sql = """
    INSERT INTO kobis_company_detail (
        company_cd, company_nm, company_nm_en, ceo_nm, parts, filmo_count
    ) VALUES (
        %(company_cd)s, %(company_nm)s, %(company_nm_en)s, %(ceo_nm)s, %(parts)s, %(filmo_count)s
    )
    ON DUPLICATE KEY UPDATE
        company_nm = VALUES(company_nm),
        company_nm_en = VALUES(company_nm_en),
        ceo_nm = VALUES(ceo_nm),
        parts = VALUES(parts),
        filmo_count = VALUES(filmo_count),
        updated_at = CURRENT_TIMESTAMP;
    """

    part_sql = """
    INSERT INTO kobis_company_part (
        company_cd, company_part_nm
    ) VALUES (
        %(company_cd)s, %(company_part_nm)s
    )
    ON DUPLICATE KEY UPDATE
        company_part_nm = VALUES(company_part_nm),
        updated_at = CURRENT_TIMESTAMP;
    """

    filmo_sql = """
    INSERT INTO kobis_company_filmo (
        company_cd, movie_cd, movie_nm, company_part_nm
    ) VALUES (
        %(company_cd)s, %(movie_cd)s, %(movie_nm)s, %(company_part_nm)s
    )
    ON DUPLICATE KEY UPDATE
        movie_nm = VALUES(movie_nm),
        company_part_nm = VALUES(company_part_nm),
        updated_at = CURRENT_TIMESTAMP;
    """

    detail_rows = []
    part_rows = []
    filmo_rows = []

    for item in details_list:
        if not item or not item.get("companyCd"):
            continue

        company_cd = item.get("companyCd")
        company_nm = item.get("companyNm")
        company_nm_en = item.get("companyNmEn")
        ceo_nm = item.get("ceoNm")
        parts = item.get("parts", [])
        filmos = item.get("filmos", [])

        part_names = [p.get("companyPartNm") for p in parts if p.get("companyPartNm")]
        parts_str = ", ".join(part_names) if part_names else None

        detail_rows.append({
            "company_cd": company_cd,
            "company_nm": company_nm,
            "company_nm_en": company_nm_en,
            "ceo_nm": ceo_nm,
            "parts": parts_str,
            "filmo_count": len(filmos),
        })

        for p in parts:
            part_nm = p.get("companyPartNm") or ""
            part_rows.append({
                "company_cd": company_cd,
                "company_part_nm": part_nm,
            })

        for f in filmos:
            movie_cd = f.get("movieCd")
            movie_nm = f.get("movieNm")
            f_part_nm = f.get("companyPartNm") or ""
            if movie_cd:
                filmo_rows.append({
                    "company_cd": company_cd,
                    "movie_cd": movie_cd,
                    "movie_nm": movie_nm,
                    "company_part_nm": f_part_nm,
                })

    with connection.cursor() as cursor:
        if detail_rows:
            cursor.executemany(company_detail_sql, detail_rows)
        if part_rows:
            cursor.executemany(part_sql, part_rows)
        if filmo_rows:
            cursor.executemany(filmo_sql, filmo_rows)

    connection.commit()


def process_company_details(connection, company_codes, batch_size=50, max_workers=10):
    """
    영화사 목록을 멀티스레드로 조회하여 배치 단위로 DB에 저장합니다.
    """
    total = len(company_codes)
    print(f"총 {total}건의 영화사 상세정보 수집 시작 (동시 스레드: {max_workers})")

    completed = 0
    start_time = time.time()

    for i in range(0, total, batch_size):
        chunk = company_codes[i:i + batch_size]
        details_list = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(fetch_kobis_company_detail, code): code for code in chunk
            }

            for future in as_completed(future_to_code):
                try:
                    detail = future.result()
                    if detail:
                        details_list.append(detail)
                except Exception as exc:
                    code = future_to_code[future]
                    print(f"영화사 [{code}] 처리 중 예외 발생: {exc}")

        if details_list:
            save_company_details_batch(connection, details_list)

        completed += len(chunk)
        elapsed = time.time() - start_time
        print(f"진행 상황: {completed}/{total} ({completed / total * 100:.1f}%) 완료 - 소요 시간: {elapsed:.1f}초")


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_detail_tables_if_not_exists(connection)

        company_codes = get_target_company_codes(connection)
        if not company_codes:
            print("kobis_company 테이블에 조회할 영화사 데이터가 없습니다.")
            return

        process_company_details(connection, company_codes, batch_size=50, max_workers=10)

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")

    finally:
        connection.close()

    print("\n영화사 상세정보 수집 및 저장 완료")


if __name__ == "__main__":
    main()

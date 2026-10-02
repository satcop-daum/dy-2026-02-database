
import json
import urllib.parse
import urllib.request
import mysql.connector

# ==============================
# KOBIS API 설정
# ==============================
KOBIS_API_KEY = "07967092cdf290d53659a8dc6b23d5da"
KOBIS_API_URL = "https://kobis.or.kr/kobisopenapi/webservice/rest/code/searchCodeList.json"

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

def fetch_kobis_common_codes(com_code):
    """
    KOBIS API에서 특정 상위코드에 해당하는 공통코드 목록을 가져옵니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "comCode": com_code,
    }
    
    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_API_URL}?{query_string}"
    
    print(f"KOBIS API 요청 URL: {request_url}")
    
    try:
        with urllib.request.urlopen(request_url) as response:
            response_body = response.read().decode("utf-8")
        data = json.loads(response_body)
        return data.get("codes", [])
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return []

def create_table_if_not_exists(connection):
    """
    공통코드 데이터를 저장할 테이블을 생성합니다.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS kobis_common_code (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        full_cd VARCHAR(20) NOT NULL,
        kor_nm VARCHAR(255),
        eng_nm VARCHAR(255),
        parent_cd VARCHAR(20),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_full_cd (full_cd)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()

def save_codes_to_db(connection, codes, parent_cd):
    """
    공통코드 데이터를 DB에 저장합니다.
    """
    if not codes:
        return

    sql = """
    INSERT INTO kobis_common_code (
        full_cd,
        kor_nm,
        eng_nm,
        parent_cd
    ) VALUES (
        %(fullCd)s,
        %(korNm)s,
        %(engNm)s,
        %(parent_cd)s
    )
    ON DUPLICATE KEY UPDATE
        kor_nm = VALUES(kor_nm),
        eng_nm = VALUES(eng_nm),
        parent_cd = VALUES(parent_cd),
        updated_at = CURRENT_TIMESTAMP;
    """
    
    rows = []
    for item in codes:
        row = {
            "fullCd": item.get("fullCd"),
            "korNm": item.get("korNm"),
            "engNm": item.get("engNm"),
            "parent_cd": parent_cd
        }
        rows.append(row)
    
    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)
    connection.commit()
    print(f"상위코드 {parent_cd}: {len(rows)}건 저장/업데이트 완료")

def main():
    # 주요 공통코드 목록 (예: 2201-영화유형, 2204-국적)
    # KOBIS에서 제공하는 주요 코드들을 순회하며 저장합니다.
    target_parent_codes = ["0105000000", "2201", "2204"] # 0105000000: 지역, 2201: 영화유형, 2204: 국적
    
    connection = mysql.connector.connect(**DB_CONFIG)
    
    try:
        create_table_if_not_exists(connection)
        
        for p_code in target_parent_codes:
            print(f"\n코드 {p_code} 조회 중...")
            codes = fetch_kobis_common_codes(p_code)
            if codes:
                save_codes_to_db(connection, codes, p_code)
            else:
                print(f"코드 {p_code}에 대한 결과가 없습니다.")
                
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
    finally:
        connection.close()

    print("\n모든 작업 완료")

if __name__ == "__main__":
    main()

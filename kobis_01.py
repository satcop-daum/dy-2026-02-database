
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import mysql.connector


# ==============================
# KOBIS API 설정
# ==============================
KOBIS_API_KEY = "07967092cdf290d53659a8dc6b23d5da"

# 일별 박스오피스 API
KOBIS_API_URL = "https://kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"


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


def get_target_date():
    """
    KOBIS 일별 박스오피스는 보통 어제 날짜 기준으로 조회합니다.
    반환 형식: YYYYMMDD
    """
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


def fetch_kobis_daily_boxoffice(target_date):
    """
    KOBIS API에서 일별 박스오피스 데이터를 가져옵니다.
    """

    params = {
        "key": KOBIS_API_KEY,
        "targetDt": target_date,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_API_URL}?{query_string}"

    print(f"KOBIS API 요청 URL: {request_url}")

    with urllib.request.urlopen(request_url) as response:
        response_body = response.read().decode("utf-8")

    data = json.loads(response_body)

    return data


def create_table_if_not_exists(connection):
    """
    KOBIS 일별 박스오피스 데이터를 저장할 테이블을 생성합니다.
    """

    sql = """
    CREATE TABLE IF NOT EXISTS kobis_daily_boxoffice (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        target_date CHAR(8) NOT NULL,
        rank_no INT,
        rank_inten INT,
        rank_old_and_new VARCHAR(10),
        movie_cd VARCHAR(20) NOT NULL,
        movie_nm VARCHAR(255),
        open_dt DATE NULL,
        sales_amt BIGINT,
        sales_share DECIMAL(10, 2),
        sales_inten BIGINT,
        sales_change DECIMAL(10, 2),
        sales_acc BIGINT,
        audi_cnt BIGINT,
        audi_inten BIGINT,
        audi_change DECIMAL(10, 2),
        audi_acc BIGINT,
        scrn_cnt INT,
        show_cnt INT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_target_movie (target_date, movie_cd)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()


def to_int(value):
    """
    문자열 숫자를 int로 변환합니다.
    빈 값이면 None 반환.
    """
    if value is None or value == "":
        return None
    return int(str(value).replace(",", ""))


def to_float(value):
    """
    문자열 숫자를 float로 변환합니다.
    빈 값이면 None 반환.
    """
    if value is None or value == "":
        return None
    return float(str(value).replace(",", ""))


def to_date(value):
    """
    YYYY-MM-DD 문자열을 DATE 타입에 맞게 반환합니다.
    빈 값이면 None 반환.
    """
    if value is None or value == "":
        return None
    return value


def save_boxoffice_to_db(connection, target_date, boxoffice_list):
    """
    KOBIS 박스오피스 데이터를 DB에 저장합니다.
    이미 같은 날짜 + 영화코드 데이터가 있으면 업데이트합니다.
    """

    sql = """
    INSERT INTO kobis_daily_boxoffice (
        target_date,
        rank_no,
        rank_inten,
        rank_old_and_new,
        movie_cd,
        movie_nm,
        open_dt,
        sales_amt,
        sales_share,
        sales_inten,
        sales_change,
        sales_acc,
        audi_cnt,
        audi_inten,
        audi_change,
        audi_acc,
        scrn_cnt,
        show_cnt
    ) VALUES (
        %(target_date)s,
        %(rank_no)s,
        %(rank_inten)s,
        %(rank_old_and_new)s,
        %(movie_cd)s,
        %(movie_nm)s,
        %(open_dt)s,
        %(sales_amt)s,
        %(sales_share)s,
        %(sales_inten)s,
        %(sales_change)s,
        %(sales_acc)s,
        %(audi_cnt)s,
        %(audi_inten)s,
        %(audi_change)s,
        %(audi_acc)s,
        %(scrn_cnt)s,
        %(show_cnt)s
    )
    ON DUPLICATE KEY UPDATE
        rank_no = VALUES(rank_no),
        rank_inten = VALUES(rank_inten),
        rank_old_and_new = VALUES(rank_old_and_new),
        movie_nm = VALUES(movie_nm),
        open_dt = VALUES(open_dt),
        sales_amt = VALUES(sales_amt),
        sales_share = VALUES(sales_share),
        sales_inten = VALUES(sales_inten),
        sales_change = VALUES(sales_change),
        sales_acc = VALUES(sales_acc),
        audi_cnt = VALUES(audi_cnt),
        audi_inten = VALUES(audi_inten),
        audi_change = VALUES(audi_change),
        audi_acc = VALUES(audi_acc),
        scrn_cnt = VALUES(scrn_cnt),
        show_cnt = VALUES(show_cnt),
        updated_at = CURRENT_TIMESTAMP;
    """

    rows = []

    for item in boxoffice_list:
        row = {
            "target_date": target_date,
            "rank_no": to_int(item.get("rank")),
            "rank_inten": to_int(item.get("rankInten")),
            "rank_old_and_new": item.get("rankOldAndNew"),
            "movie_cd": item.get("movieCd"),
            "movie_nm": item.get("movieNm"),
            "open_dt": to_date(item.get("openDt")),
            "sales_amt": to_int(item.get("salesAmt")),
            "sales_share": to_float(item.get("salesShare")),
            "sales_inten": to_int(item.get("salesInten")),
            "sales_change": to_float(item.get("salesChange")),
            "sales_acc": to_int(item.get("salesAcc")),
            "audi_cnt": to_int(item.get("audiCnt")),
            "audi_inten": to_int(item.get("audiInten")),
            "audi_change": to_float(item.get("audiChange")),
            "audi_acc": to_int(item.get("audiAcc")),
            "scrn_cnt": to_int(item.get("scrnCnt")),
            "show_cnt": to_int(item.get("showCnt")),
        }

        rows.append(row)

    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)

    connection.commit()

    print(f"{len(rows)}건 저장 완료")


def main():
    target_date = get_target_date()

    print(f"조회 기준일: {target_date}")

    data = fetch_kobis_daily_boxoffice(target_date)

    boxoffice_result = data.get("boxOfficeResult", {})
    boxoffice_list = boxoffice_result.get("dailyBoxOfficeList", [])

    if not boxoffice_list:
        print("저장할 박스오피스 데이터가 없습니다.")
        return

    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_table_if_not_exists(connection)
        save_boxoffice_to_db(connection, target_date, boxoffice_list)
    finally:
        connection.close()

    print("작업 완료")


if __name__ == "__main__":
    main()
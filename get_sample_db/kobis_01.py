
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import mysql.connector

from config_api import KOBIS_API_KEY
from config_db import DB_CONFIG

# 일별 박스오피스 API
KOBIS_API_URL = "https://kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

def fetch_kobis_daily_boxoffice(target_date, max_retries=3):
    """
    KOBIS API에서 일별 박스오피스 데이터를 가져옵니다.
    """

    params = {
        "key": KOBIS_API_KEY,
        "targetDt": target_date,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_API_URL}?{query_string}"

    print(f"[{target_date}] KOBIS API 요청 URL: {request_url}")

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                request_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8")

            data = json.loads(response_body)
            return data
        except Exception as e:
            print(f"[{target_date}] API 요청 중 오류 발생 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1)
            else:
                return {}

    return {}


def create_table_if_not_exists(connection):
    """
    KOBIS 일별 박스오피스 데이터를 저장할 테이블을 생성합니다.
    """

    sql = """
    CREATE TABLE IF NOT EXISTS kobis_daily_boxoffice (
        id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '고유 식별자',
        target_date CHAR(8) NOT NULL COMMENT '대상 상영일자',
        rank_no INT COMMENT '해당일자의 박스오피스 순위',
        rank_inten INT COMMENT '전일대비 순위의 증감분',
        rank_old_and_new VARCHAR(10) COMMENT '랭킹에 신규진입여부 (OLD : 기존, NEW : 신규)',
        movie_cd VARCHAR(20) NOT NULL COMMENT '영화의 대표코드',
        movie_nm VARCHAR(255) COMMENT '영화명(국문)',
        open_dt DATE NULL COMMENT '영화의 개봉일',
        sales_amt BIGINT COMMENT '해당일의 매출액',
        sales_share DECIMAL(10, 2) COMMENT '해당일자 상영작의 매출총액 대비 해당 영화의 매출비율',
        sales_inten BIGINT COMMENT '전일 대비 매출액 증감분',
        sales_change DECIMAL(10, 2) COMMENT '전일 대비 매출액 증감 비율',
        sales_acc BIGINT COMMENT '누적매출액',
        audi_cnt BIGINT COMMENT '해당일의 관객수',
        audi_inten BIGINT COMMENT '전일 대비 관객수 증감분',
        audi_change DECIMAL(10, 2) COMMENT '전일 대비 관객수 증감 비율',
        audi_acc BIGINT COMMENT '누적관객수',
        scrn_cnt INT COMMENT '해당일자에 해당영화가 상영된 스크린수',
        show_cnt INT COMMENT '해당일자에 해당영화가 상영된 횟수',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
        UNIQUE KEY uk_target_movie (target_date, movie_cd)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='일별 박스오피스';
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()


def truncate_table(connection):
    """
    kobis_daily_boxoffice 테이블 데이터를 초기화합니다.
    """
    sql = "TRUNCATE TABLE kobis_daily_boxoffice"

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()
    print("kobis_daily_boxoffice 테이블 초기화 완료")


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

    print(f"[{target_date}] {len(rows)}건 저장 완료")


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_table_if_not_exists(connection)
        truncate_table(connection)

        start_date = date(2026, 1, 1)
        # 박스오피스 데이터는 보통 전날까지 집계되므로 어제 또는 오늘 날짜까지 조회
        end_date = (datetime.now() - timedelta(days=1)).date()

        current_date = start_date
        total_saved_days = 0

        while current_date <= end_date:
            target_date = current_date.strftime("%Y%m%d")
            try:
                data = fetch_kobis_daily_boxoffice(target_date)

                boxoffice_result = data.get("boxOfficeResult", {})
                boxoffice_list = boxoffice_result.get("dailyBoxOfficeList", [])

                if boxoffice_list:
                    save_boxoffice_to_db(connection, target_date, boxoffice_list)
                    total_saved_days += 1
                else:
                    print(f"[{target_date}] 저장할 박스오피스 데이터가 없습니다.")
            except Exception as e:
                print(f"[{target_date}] 처리 중 오류 발생 (무시하고 계속 진행): {e}")
                try:
                    connection.rollback()
                except Exception:
                    pass

            current_date += timedelta(days=1)

        print(f"\n총 {total_saved_days}일간의 박스오피스 데이터 수집 완료")

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")

    finally:
        connection.close()

    print("모든 작업 완료")


if __name__ == "__main__":
    main()
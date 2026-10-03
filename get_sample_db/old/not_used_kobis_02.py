import json
import urllib.parse
import urllib.request

import mysql.connector

from get_sample_db.config_api import KOBIS_API_KEY
from get_sample_db.config_db import DB_CONFIG

# 영화목록 조회 API
KOBIS_MOVIE_LIST_API_URL = (
    "https://kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"
)

def fetch_kobis_movie_list(cur_page=1, item_per_page=100):
    """
    KOBIS 영화목록 조회 API에서 영화 목록 데이터를 가져옵니다.
    """

    params = {
        "key": KOBIS_API_KEY,
        "curPage": cur_page,
        "itemPerPage": item_per_page,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_MOVIE_LIST_API_URL}?{query_string}"

    print(f"KOBIS 영화목록 API 요청 URL: {request_url}")

    with urllib.request.urlopen(request_url) as response:
        response_body = response.read().decode("utf-8")

    data = json.loads(response_body)

    return data


def create_table_if_not_exists(connection):
    """
    KOBIS 영화목록 데이터를 저장할 테이블을 생성합니다.
    """

    sql = """
    CREATE TABLE IF NOT EXISTS kobis_movie_list (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        movie_cd VARCHAR(20) NOT NULL,
        movie_nm VARCHAR(255),
        movie_nm_en VARCHAR(255),
        prdt_year VARCHAR(10),
        open_dt VARCHAR(20),
        type_nm VARCHAR(100),
        prdt_stat_nm VARCHAR(100),
        nation_alt VARCHAR(255),
        genre_alt VARCHAR(255),
        rep_nation_nm VARCHAR(100),
        rep_genre_nm VARCHAR(100),
        directors TEXT,
        companys TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_movie_cd (movie_cd)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

    connection.commit()


def list_to_names(items, name_key):
    """
    리스트 형태 데이터를 이름 문자열로 변환합니다.
    """

    if not items:
        return None

    names = []

    for item in items:
        name = item.get(name_key)
        if name:
            names.append(name)

    if not names:
        return None

    return ", ".join(names)


def save_movie_list_to_db(connection, movie_list):
    """
    KOBIS 영화목록 데이터를 DB에 저장합니다.
    같은 movie_cd가 있으면 업데이트합니다.
    """

    sql = """
    INSERT INTO kobis_movie_list (
        movie_cd,
        movie_nm,
        movie_nm_en,
        prdt_year,
        open_dt,
        type_nm,
        prdt_stat_nm,
        nation_alt,
        genre_alt,
        rep_nation_nm,
        rep_genre_nm,
        directors,
        companys
    ) VALUES (
        %(movie_cd)s,
        %(movie_nm)s,
        %(movie_nm_en)s,
        %(prdt_year)s,
        %(open_dt)s,
        %(type_nm)s,
        %(prdt_stat_nm)s,
        %(nation_alt)s,
        %(genre_alt)s,
        %(rep_nation_nm)s,
        %(rep_genre_nm)s,
        %(directors)s,
        %(companys)s
    )
    ON DUPLICATE KEY UPDATE
        movie_nm = VALUES(movie_nm),
        movie_nm_en = VALUES(movie_nm_en),
        prdt_year = VALUES(prdt_year),
        open_dt = VALUES(open_dt),
        type_nm = VALUES(type_nm),
        prdt_stat_nm = VALUES(prdt_stat_nm),
        nation_alt = VALUES(nation_alt),
        genre_alt = VALUES(genre_alt),
        rep_nation_nm = VALUES(rep_nation_nm),
        rep_genre_nm = VALUES(rep_genre_nm),
        directors = VALUES(directors),
        companys = VALUES(companys),
        updated_at = CURRENT_TIMESTAMP;
    """

    rows = []

    for item in movie_list:
        row = {
            "movie_cd": item.get("movieCd"),
            "movie_nm": item.get("movieNm"),
            "movie_nm_en": item.get("movieNmEn"),
            "prdt_year": item.get("prdtYear"),
            "open_dt": item.get("openDt"),
            "type_nm": item.get("typeNm"),
            "prdt_stat_nm": item.get("prdtStatNm"),
            "nation_alt": item.get("nationAlt"),
            "genre_alt": item.get("genreAlt"),
            "rep_nation_nm": item.get("repNationNm"),
            "rep_genre_nm": item.get("repGenreNm"),
            "directors": list_to_names(item.get("directors"), "peopleNm"),
            "companys": list_to_names(item.get("companys"), "companyNm"),
        }

        if row["movie_cd"]:
            rows.append(row)

    if not rows:
        print("저장할 영화목록 데이터가 없습니다.")
        return

    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)

    connection.commit()

    print(f"{len(rows)}건 저장 완료")


def fetch_and_save_pages(connection, start_page=1, end_page=5, item_per_page=100):
    """
    여러 페이지의 영화목록 데이터를 가져와서 저장합니다.
    """

    total_saved_pages = 0

    for cur_page in range(start_page, end_page + 1):
        print("=" * 60)
        print(f"{cur_page}페이지 조회 시작")

        data = fetch_kobis_movie_list(
            cur_page=cur_page,
            item_per_page=item_per_page,
        )

        movie_list_result = data.get("movieListResult", {})
        movie_list = movie_list_result.get("movieList", [])

        if not movie_list:
            print(f"{cur_page}페이지에 영화 데이터가 없습니다. 종료합니다.")
            break

        save_movie_list_to_db(connection, movie_list)
        total_saved_pages += 1

    print("=" * 60)
    print(f"총 {total_saved_pages}개 페이지 처리 완료")


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        create_table_if_not_exists(connection)

        fetch_and_save_pages(
            connection=connection,
            start_page=1,
            end_page=5,
            item_per_page=100,
        )

    finally:
        connection.close()

    print("작업 완료")


if __name__ == "__main__":
    main()
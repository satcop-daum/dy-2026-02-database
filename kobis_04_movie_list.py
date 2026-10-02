
import json
import urllib.parse
import urllib.request
import mysql.connector

# ==============================
# KOBIS API 설정
# ==============================
KOBIS_API_KEY = "07967092cdf290d53659a8dc6b23d5da"
# 영화목록 API
KOBIS_MOVIE_LIST_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"

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

def fetch_kobis_movie_list(cur_page=1, item_per_page=100):
    """
    KOBIS API에서 영화목록을 가져옵니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "curPage": cur_page,
        "itemPerPage": item_per_page,
    }
    
    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_MOVIE_LIST_URL}?{query_string}"
    
    print(f"KOBIS API 요청 URL: {request_url}")
    
    try:
        with urllib.request.urlopen(request_url) as response:
            response_body = response.read().decode("utf-8")
        data = json.loads(response_body)
        return data.get("movieListResult", {})
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return {}

def create_table_if_not_exists(connection):
    """
    영화목록 데이터를 저장할 테이블을 생성합니다.
    """
    sql = """
    CREATE TABLE IF NOT EXISTS kobis_movie_info (
        movie_cd VARCHAR(20) PRIMARY KEY,
        movie_nm VARCHAR(255),
        movie_nm_en VARCHAR(255),
        prdt_year VARCHAR(4),
        open_dt VARCHAR(8),
        type_nm VARCHAR(50),
        prdt_stat_nm VARCHAR(50),
        nation_alt VARCHAR(255),
        genre_alt VARCHAR(255),
        rep_nation_nm VARCHAR(100),
        rep_genre_nm VARCHAR(100),
        directors TEXT,
        companys TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()

def save_movies_to_db(connection, movie_list):
    """
    영화목록 데이터를 DB에 저장합니다.
    """
    if not movie_list:
        return

    sql = """
    INSERT INTO kobis_movie_info (
        movie_cd, movie_nm, movie_nm_en, prdt_year, open_dt,
        type_nm, prdt_stat_nm, nation_alt, genre_alt,
        rep_nation_nm, rep_genre_nm, directors, companys
    ) VALUES (
        %(movieCd)s, %(movieNm)s, %(movieNmEn)s, %(prdtYear)s, %(openDt)s,
        %(typeNm)s, %(prdtStatNm)s, %(nationAlt)s, %(genreAlt)s,
        %(repNationNm)s, %(repGenreNm)s, %(directors)s, %(companys)s
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
        # 감독 정보 처리 (리스트를 쉼표로 구분된 문자열로 변환)
        directors = item.get("directors", [])
        dir_names = [d.get("peopleNm") for d in directors if d.get("peopleNm")]
        dir_str = ", ".join(dir_names)
        
        # 제작사 정보 처리
        companys = item.get("companys", [])
        comp_names = [c.get("companyNm") for c in companys if c.get("companyNm")]
        comp_str = ", ".join(comp_names)

        row = {
            "movieCd": item.get("movieCd"),
            "movieNm": item.get("movieNm"),
            "movieNmEn": item.get("movieNmEn"),
            "prdtYear": item.get("prdtYear"),
            "openDt": item.get("openDt"),
            "typeNm": item.get("typeNm"),
            "prdtStatNm": item.get("prdtStatNm"),
            "nationAlt": item.get("nationAlt"),
            "genreAlt": item.get("genreAlt"),
            "repNationNm": item.get("repNationNm"),
            "repGenreNm": item.get("repGenreNm"),
            "directors": dir_str,
            "companys": comp_str
        }
        rows.append(row)
    
    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)
    connection.commit()
    print(f"{len(rows)}건의 영화 정보 저장/업데이트 완료")

def main():
    connection = mysql.connector.connect(**DB_CONFIG)
    
    try:
        create_table_if_not_exists(connection)
        
        # 최근 5페이지 정도 가져와 봅니다 (페이지당 100건, 총 500건)
        for page in range(1, 6):
            print(f"\n{page}페이지 조회 중...")
            result = fetch_kobis_movie_list(cur_page=page, item_per_page=100)
            movie_list = result.get("movieList", [])
            
            if movie_list:
                save_movies_to_db(connection, movie_list)
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

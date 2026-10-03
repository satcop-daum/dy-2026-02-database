import json
import math
import time
import urllib.parse
import urllib.request
import mysql.connector

from config_api import KOBIS_API_KEY
from config_db import DB_CONFIG

# 영화목록 API
KOBIS_MOVIE_LIST_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"

def fetch_kobis_movie_list(cur_page=1, item_per_page=100, max_retries=3):
    """
    KOBIS API에서 영화목록을 가져옵니다.
    네트워크 오류 또는 일시적 장애 시 재시도합니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "curPage": cur_page,
        "itemPerPage": item_per_page,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_MOVIE_LIST_URL}?{query_string}"

    print(f"KOBIS API 요청 URL: {request_url}")

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                request_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8")
            data = json.loads(response_body)
            return data.get("movieListResult", {})
        except Exception as e:
            print(f"API 요청 중 오류 발생 (시도 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(1)
            else:
                return {}
    return {}


def save_movies_to_db(connection, movie_list):
    """
    영화목록 데이터를 DB에 저장합니다.
    모든 응답 필드(movieCd, movieNm, movieNmEn, prdtYear, openDt, prdtStatNm, typeNm)만 누락 없이 저장합니다.
    """
    if not movie_list:
        print("저장할 영화목록 데이터가 없습니다.")
        return 0

    sql = """
        INSERT INTO kobis_movie 
        (
            movie_cd
            , movie_nm
            , movie_nm_en
            , prdt_year
            , open_dt
            , prdt_stat_nm
            , type_nm
        )
        VALUES 
        (
            %(movie_cd)s
            , %(movie_nm)s
            , %(movie_nm_en)s
            , %(prdt_year)s
            , %(open_dt)s
            , %(prdt_stat_nm)s  
            , %(type_nm)s
        ) 
        ON DUPLICATE KEY UPDATE 
            movie_nm = VALUES (movie_nm)
            , movie_nm_en = VALUES (movie_nm_en)
            , prdt_year = VALUES (prdt_year)
            , open_dt = VALUES (open_dt)
            , prdt_stat_nm = VALUES (prdt_stat_nm)
            , type_nm = VALUES (type_nm) 
            , updated_at = CURRENT_TIMESTAMP; 
          """

    rows = []
    for item in movie_list:
        movie_cd = item.get("movieCd")
        if not movie_cd:
            continue

        # 감독 정보 처리 (peopleNm 추출 및 directors / people_nm 에 저장)
        directors = item.get("directors", [])
        dir_names = [d.get("peopleNm") for d in directors if d.get("peopleNm")]
        people_nm_str = ", ".join(dir_names) if dir_names else None
        directors_str = people_nm_str

        # 제작사 정보 처리 (companyCd, companyNm 추출 및 companys, company_cd, company_nm 에 저장)
        companys = item.get("companys", [])
        comp_cds = [c.get("companyCd") for c in companys if c.get("companyCd")]
        comp_nms = [c.get("companyNm") for c in companys if c.get("companyNm")]

        company_cd_str = ", ".join(comp_cds) if comp_cds else None
        company_nm_str = ", ".join(comp_nms) if comp_nms else None

        comp_combined = []
        for c in companys:
            cd = c.get("companyCd", "").strip() if c.get("companyCd") else ""
            nm = c.get("companyNm", "").strip() if c.get("companyNm") else ""
            if cd and nm:
                comp_combined.append(f"{nm}({cd})")
            elif nm:
                comp_combined.append(nm)
            elif cd:
                comp_combined.append(cd)
        companys_str = ", ".join(comp_combined) if comp_combined else company_nm_str

        row = {
            "movie_cd": movie_cd,
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
            "directors": directors_str,
            "people_nm": people_nm_str,
            "companys": companys_str,
            "company_cd": company_cd_str,
            "company_nm": company_nm_str,
        }
        rows.append(row)

    if not rows:
        print("저장할 영화목록 데이터가 없습니다.")
        return 0

    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)
        row_count = cursor.rowcount
    connection.commit()
    print(f"DB insert 실행 결과: {row_count}건 반영 완료 ({len(rows)}건 데이터)")
    return row_count


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        item_per_page = 100
        total_saved_count = 0

        # 1페이지 조회 및 전체 개수(totCnt) 확인
        print("\n1페이지 조회 중...")
        result = fetch_kobis_movie_list(cur_page=1, item_per_page=item_per_page)
        tot_cnt = int(result.get("totCnt", 0))
        movie_list = result.get("movieList", [])

        if movie_list:
            save_movies_to_db(connection, movie_list)
            total_saved_count += len(movie_list)

        total_pages = math.ceil(tot_cnt / item_per_page) if item_per_page else 1
        print(f"\n전체 영화 개수: {tot_cnt}건, 총 페이지 수: {total_pages}페이지")
        print(f"누적 저장 데이터 수: {total_saved_count}/{tot_cnt}건")

        # 2페이지부터 마지막 페이지까지 순차 조회
        for page in range(2, total_pages + 1):
            print(f"\n{page}/{total_pages}페이지 조회 중...")
            try:
                result = fetch_kobis_movie_list(cur_page=page, item_per_page=item_per_page)
                if not result:
                    print(f"{page}페이지 데이터를 가져오지 못했습니다. 다음 페이지로 진행합니다.")
                    continue

                movie_list = result.get("movieList", [])

                if movie_list:
                    save_movies_to_db(connection, movie_list)
                    total_saved_count += len(movie_list)
                    print(f"누적 저장 데이터 수: {total_saved_count}/{tot_cnt}건")
                else:
                    print("더 이상 데이터가 없습니다.")
                    break
            except Exception as e:
                print(f"[{page}페이지] 처리 중 오류 발생 (무시하고 계속 진행): {e}")
                try:
                    connection.rollback()
                except Exception:
                    pass

        print(f"\n총 {total_saved_count}건의 영화 정보 처리 완료")

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
    finally:
        connection.close()

    print("\n모든 작업 완료")


if __name__ == "__main__":
    main()

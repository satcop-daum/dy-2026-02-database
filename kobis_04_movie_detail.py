import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import mysql.connector

from config_api import KOBIS_API_KEY
from config_db import DB_CONFIG


# 영화 상세정보 API URL (action_movie.md 참조)
KOBIS_MOVIE_INFO_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
)

def fetch_kobis_movie_detail(movie_cd, max_retries=3):
    """
    KOBIS API에서 특정 영화의 상세정보를 조회합니다.
    """
    params = {
        "key": KOBIS_API_KEY,
        "movieCd": movie_cd,
    }

    query_string = urllib.parse.urlencode(params)
    request_url = f"{KOBIS_MOVIE_INFO_URL}?{query_string}"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                request_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode("utf-8")

            data = json.loads(response_body)
            return data.get("movieInfoResult", {}).get("movieInfo", {})

        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5 * attempt)
            else:
                print(f"[{movie_cd}] 영화 상세정보 API 조회 실패: {e}")
                return {}

    return {}

def get_target_movie_codes(connection, limit=None):
    """
    kobis_movie_info 테이블에서 조회 대상 영화 코드 목록을 가져옵니다.
    """
    sql = "SELECT movie_cd FROM kobis_movie ORDER BY movie_cd"
    if limit:
        sql += f" LIMIT {limit}"

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    return [row[0] for row in rows]

def save_movie_details_batch(connection, details_list):
    """
    영화 상세정보 및 하위 테이블 데이터 목록을 DB에 일괄 저장합니다.
    """
    if not details_list:
        return

    detail_sql = """
    INSERT INTO kobis_movie (
        movie_cd, movie_nm, movie_nm_en, movie_nm_og, prdt_year,
        show_tm, open_dt, prdt_stat_nm, type_nm,
        audits
    ) VALUES (
        %(movie_cd)s, %(movie_nm)s, %(movie_nm_en)s, %(movie_nm_og)s, %(prdt_year)s,
        %(show_tm)s, %(open_dt)s, %(prdt_stat_nm)s, %(type_nm)s,
        %(audits)s
    )
    ON DUPLICATE KEY UPDATE
        movie_nm = VALUES(movie_nm),
        movie_nm_en = VALUES(movie_nm_en),
        movie_nm_og = VALUES(movie_nm_og),
        prdt_year = VALUES(prdt_year),
        show_tm = VALUES(show_tm),
        open_dt = VALUES(open_dt),
        prdt_stat_nm = VALUES(prdt_stat_nm),
        type_nm = VALUES(type_nm),        
        audits = VALUES(audits),        
        updated_at = CURRENT_TIMESTAMP;
    """

    director_sql = """
    INSERT INTO kobis_movie_director (
        movie_cd, people_nm, people_nm_en
    ) VALUES (
        %(movie_cd)s, %(people_nm)s, %(people_nm_en)s
    )
    ON DUPLICATE KEY UPDATE
        people_nm_en = VALUES(people_nm_en),
        updated_at = CURRENT_TIMESTAMP;
    """

    actor_sql = """
    INSERT INTO kobis_movie_actor (
        movie_cd, people_nm, people_nm_en, cast, cast_en
    ) VALUES (
        %(movie_cd)s, %(people_nm)s, %(people_nm_en)s, %(cast)s, %(cast_en)s
    )
    """

    company_sql = """
    INSERT INTO kobis_movie_company (
        movie_cd, company_cd, company_nm, company_nm_en, company_part_nm
    ) VALUES (
        %(movie_cd)s, %(company_cd)s, %(company_nm)s, %(company_nm_en)s, %(company_part_nm)s
    )
    """

    audit_sql = """
    INSERT INTO kobis_movie_audit (
        movie_cd, audit_no, watch_grade_nm
    ) VALUES (
        %(movie_cd)s, %(audit_no)s, %(watch_grade_nm)s
    )
    """

    staff_sql = """
    INSERT INTO kobis_movie_staff (
        movie_cd, people_nm, people_nm_en, staff_role_nm
    ) VALUES (
        %(movie_cd)s, %(people_nm)s, %(people_nm_en)s, %(staff_role_nm)s
    )
    """

    show_type_sql = """
    INSERT INTO kobis_movie_show_type (
        movie_cd, show_type_group_nm, show_type_nm
    ) VALUES (
        %(movie_cd)s, %(show_type_group_nm)s, %(show_type_nm)s
    )
    """

    nation_sql = """
    INSERT INTO kobis_movie_nation (
        movie_cd, nation_nm
    ) VALUES (
        %(movie_cd)s, %(nation_nm)s
    )
    ON DUPLICATE KEY UPDATE
        updated_at = CURRENT_TIMESTAMP;
    """

    genre_sql = """
    INSERT INTO kobis_movie_genre (
        movie_cd, genre_nm
    ) VALUES (
        %(movie_cd)s, %(genre_nm)s
    )
    ON DUPLICATE KEY UPDATE
        updated_at = CURRENT_TIMESTAMP;
    """

    detail_rows = []
    director_rows = []
    actor_rows = []
    company_rows = []
    audit_rows = []
    staff_rows = []
    show_type_rows = []
    nation_rows = []
    genre_rows = []

    movie_cds_to_clear_children = []

    for item in details_list:
        if not item or not item.get("movieCd"):
            continue

        movie_cd = item.get("movieCd")
        movie_cds_to_clear_children.append(movie_cd)

        nations = item.get("nations", [])
        genres = item.get("genres", [])
        directors = item.get("directors", [])
        actors = item.get("actors", [])
        show_types = item.get("showTypes", [])
        audits = item.get("audits", [])
        companys = item.get("companys", [])
        staffs = item.get("staffs", [])

        nation_names = [n.get("nationNm") for n in nations if n.get("nationNm")]
        genre_names = [g.get("genreNm") for g in genres if g.get("genreNm")]
        director_names = [d.get("peopleNm") for d in directors if d.get("peopleNm")]
        actor_names = [
            f"{a.get('peopleNm')}({a.get('cast')})" if a.get("cast") else a.get("peopleNm")
            for a in actors if a.get("peopleNm")
        ]
        show_type_names = [
            f"{st.get('showTypeGroupNm')}-{st.get('showTypeNm')}" if st.get("showTypeGroupNm") else st.get("showTypeNm")
            for st in show_types if st.get("showTypeNm") or st.get("showTypeGroupNm")
        ]
        audit_names = [
            f"{au.get('watchGradeNm')}({au.get('auditNo')})" if au.get("auditNo") else au.get("watchGradeNm")
            for au in audits if au.get("watchGradeNm") or au.get("auditNo")
        ]
        company_names = [
            f"{c.get('companyNm')}[{c.get('companyPartNm')}]" if c.get("companyPartNm") else c.get("companyNm")
            for c in companys if c.get("companyNm")
        ]
        staff_names = [
            f"{s.get('peopleNm')}({s.get('staffRoleNm')})" if s.get("staffRoleNm") else s.get("peopleNm")
            for s in staffs if s.get("peopleNm")
        ]

        detail_rows.append({
            "movie_cd": movie_cd,
            "movie_nm": item.get("movieNm"),
            "movie_nm_en": item.get("movieNmEn"),
            "movie_nm_og": item.get("movieNmOg"),
            "prdt_year": item.get("prdtYear"),
            "show_tm": item.get("showTm"),
            "open_dt": item.get("openDt"),
            "prdt_stat_nm": item.get("prdtStatNm"),
            "type_nm": item.get("typeNm"),
            "nations": ", ".join(nation_names) if nation_names else None,
            "genres": ", ".join(genre_names) if genre_names else None,
            "directors": ", ".join(director_names) if director_names else None,
            "actors": ", ".join(actor_names) if actor_names else None,
            "show_types": ", ".join(show_type_names) if show_type_names else None,
            "audits": ", ".join(audit_names) if audit_names else None,
            "companys": ", ".join(company_names) if company_names else None,
            "staffs": ", ".join(staff_names) if staff_names else None,
        })

        for d in directors:
            if d.get("peopleNm"):
                director_rows.append({
                    "movie_cd": movie_cd,
                    "people_nm": d.get("peopleNm"),
                    "people_nm_en": d.get("peopleNmEn"),
                })

        for a in actors:
            if a.get("peopleNm"):
                actor_rows.append({
                    "movie_cd": movie_cd,
                    "people_nm": a.get("peopleNm"),
                    "people_nm_en": a.get("peopleNmEn"),
                    "cast": a.get("cast"),
                    "cast_en": a.get("castEn"),
                })

        for c in companys:
            if c.get("companyNm") or c.get("companyCd"):
                company_rows.append({
                    "movie_cd": movie_cd,
                    "company_cd": c.get("companyCd"),
                    "company_nm": c.get("companyNm"),
                    "company_nm_en": c.get("companyNmEn"),
                    "company_part_nm": c.get("companyPartNm"),
                })

        for au in audits:
            if au.get("auditNo") or au.get("watchGradeNm"):
                audit_rows.append({
                    "movie_cd": movie_cd,
                    "audit_no": au.get("auditNo"),
                    "watch_grade_nm": au.get("watchGradeNm"),
                })

        for s in staffs:
            if s.get("peopleNm"):
                staff_rows.append({
                    "movie_cd": movie_cd,
                    "people_nm": s.get("peopleNm"),
                    "people_nm_en": s.get("peopleNmEn"),
                    "staff_role_nm": s.get("staffRoleNm"),
                })

        for st in show_types:
            if st.get("showTypeGroupNm") or st.get("showTypeNm"):
                show_type_rows.append({
                    "movie_cd": movie_cd,
                    "show_type_group_nm": st.get("showTypeGroupNm"),
                    "show_type_nm": st.get("showTypeNm"),
                })

        for n in nations:
            if n.get("nationNm"):
                nation_rows.append({
                    "movie_cd": movie_cd,
                    "nation_nm": n.get("nationNm"),
                })

        for g in genres:
            if g.get("genreNm"):
                genre_rows.append({
                    "movie_cd": movie_cd,
                    "genre_nm": g.get("genreNm"),
                })

    with connection.cursor() as cursor:
        if movie_cds_to_clear_children:
            format_strings = ','.join(['%s'] * len(movie_cds_to_clear_children))
            # 기존 하위 데이터 중복 방지를 위해 삭제 후 재삽입
            cursor.execute(f"DELETE FROM kobis_movie_actor WHERE movie_cd IN ({format_strings})", tuple(movie_cds_to_clear_children))
            cursor.execute(f"DELETE FROM kobis_movie_company WHERE movie_cd IN ({format_strings})", tuple(movie_cds_to_clear_children))
            cursor.execute(f"DELETE FROM kobis_movie_audit WHERE movie_cd IN ({format_strings})", tuple(movie_cds_to_clear_children))
            cursor.execute(f"DELETE FROM kobis_movie_staff WHERE movie_cd IN ({format_strings})", tuple(movie_cds_to_clear_children))
            cursor.execute(f"DELETE FROM kobis_movie_show_type WHERE movie_cd IN ({format_strings})", tuple(movie_cds_to_clear_children))

        if detail_rows:
            cursor.executemany(detail_sql, detail_rows)
        if director_rows:
            cursor.executemany(director_sql, director_rows)
        if actor_rows:
            cursor.executemany(actor_sql, actor_rows)
        if company_rows:
            cursor.executemany(company_sql, company_rows)
        if audit_rows:
            cursor.executemany(audit_sql, audit_rows)
        if staff_rows:
            cursor.executemany(staff_sql, staff_rows)
        if show_type_rows:
            cursor.executemany(show_type_sql, show_type_rows)
        if nation_rows:
            cursor.executemany(nation_sql, nation_rows)
        if genre_rows:
            cursor.executemany(genre_sql, genre_rows)

    connection.commit()

def process_movie_details(connection, movie_codes, batch_size=50, max_workers=10):
    """
    영화 목록을 멀티스레드로 조회하여 배치 단위로 DB에 저장합니다.
    """
    total = len(movie_codes)
    print(f"총 {total}건의 영화 상세정보 수집 시작 (동시 스레드: {max_workers})")

    completed = 0
    start_time = time.time()

    for i in range(0, total, batch_size):
        chunk = movie_codes[i:i + batch_size]
        details_list = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(fetch_kobis_movie_detail, code): code for code in chunk
            }

            for future in as_completed(future_to_code):
                try:
                    detail = future.result()
                    if detail:
                        details_list.append(detail)
                except Exception as exc:
                    code = future_to_code[future]
                    print(f"영화 [{code}] 처리 중 예외 발생: {exc}")

        if details_list:
            try:
                save_movie_details_batch(connection, details_list)
            except Exception as e:
                print(f"배치 저장 중 오류 발생: {e}")
                connection.rollback()

        completed += len(chunk)
        elapsed = time.time() - start_time
        print(f"진행 상황: {completed}/{total} ({completed / total * 100:.1f}%) 완료 - 소요 시간: {elapsed:.1f}초")


def main():
    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        movie_codes = get_target_movie_codes(connection)
        if not movie_codes:
            print("kobis_movie_info 테이블에 조회할 영화 데이터가 없습니다.")
            return

        process_movie_details(connection, movie_codes, batch_size=50, max_workers=10)

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")

    finally:
        connection.close()

    print("\n영화 상세정보 수집 및 저장 완료")


if __name__ == "__main__":
    main()

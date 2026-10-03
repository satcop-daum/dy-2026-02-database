영화상세정보 조회 API 서비스
통합전산망에서 사용되는 영화상세정보를 영화코드를 통해 조회합니다.
REST/SOAP 방식 중 선택적으로 호출가능하며 REST 방식의 응답형식은 XML과 JSON을 지원합니다.( URI의 extension으로 구분)

1. REST 방식

기본 요청 URL : http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.xml (또는 .json)
요청 parameter : 3번항의 요청 인터페이스 정보를 참조하여 GET 방식으로 호출
2. SOAP 방식

요청 URL : http://www.kobis.or.kr/kobisopenapi/webservice/soap/movie
WSDL URL : http://www.kobis.or.kr/kobisopenapi/webservice/soap/movie?wsdl
Operation : searchMovieInfo

3. 인터페이스

요청 인터페이스
요청 변수	값	설명
key	문자열(필수)	발급받은키 값을 입력합니다.
movieCd	문자열(필수)	영화코드를 지정합니다.
응답 구조
응답 필드	값	설명
movieCd	문자열	영화코드를 출력합니다.
movieNm	문자열	영화명(국문)을 출력합니다.
movieNmEn	문자열	영화명(영문)을 출력합니다.
movieNmOg	문자열	영화명(원문)을 출력합니다.
prdtYear	문자열	제작연도를 출력합니다.
showTm	문자열	상영시간을 출력합니다.
openDt	문자열	개봉연도를 출력합니다.
prdtStatNm	문자열	제작상태명을 출력합니다.
typeNm	문자열	영화유형명을 출력합니다.
nations	문자열	제작국가를 나타냅니다.
nationNm	문자열	제작국가명을 출력합니다.
genreNm	문자열	장르명을 출력합니다.
directors	문자열	감독을 나타냅니다.
peopleNm	문자열	감독명을 출력합니다.
peopleNmEn	문자열	감독명(영문)을 출력합니다.
actors	문자열	배우를 나타냅니다.
peopleNm	문자열	배우명을 출력합니다.
peopleNmEn	문자열	배우명(영문)을 출력합니다.
cast	문자열	배역명을 출력합니다.
castEn	문자열	배역명(영문)을 출력합니다.
showTypes	문자열	상영형태 구분을 나타냅니다.
showTypeGroupNm	문자열	상영형태 구분을 출력합니다.
showTypeNm	문자열	상영형태명을 출력합니다.
audits	문자열	심의정보를 나타냅니다.
auditNo	문자열	심의번호를 출력합니다.
watchGradeNm	문자열	관람등급 명칭을 출력합니다.
companys	문자열	참여 영화사를 나타냅니다.
companyCd	문자열	참여 영화사 코드를 출력합니다.
companyNm	문자열	참여 영화사명을 출력합니다.
companyNmEn	문자열	참여 영화사명(영문)을 출력합니다.
companyPartNm	문자열	참여 영화사 분야명을 출력합니다.
staffs	문자열	스텝을 나타냅니다.
peopleNm	문자열	스텝명을 출력합니다.
peopleNmEn	문자열	스텝명(영문)을 출력합니다.
staffRoleNm	문자열	스텝역할명을 출력합니다.
4. 응답 예시

XML	http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.xml?key=82ca741a2844c5c180a208137bb92bd7&movieCd=20124079
JSON	http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json?key=82ca741a2844c5c180a208137bb92bd7&movieCd=20124079

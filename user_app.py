import streamlit as st
import math
import re
import random

from database_user import LearningRepo

st.set_page_config(page_title="AI 영어뉴스 학습자 페이지", layout="wide")

# --- 유틸리티 함수 ---
def make_blanks(text, ratio=0.5):
    def replace_match(match):
        word = match.group()
        if len(word) > 2 and random.random() < ratio:
            return "_" * len(word)
        return word
    # r'\w+' : 알파벳, 숫자, 언더바(_) 등만 바꾸고 문장부호, 공백은 매칭되지 않음
    return re.sub(r'\w+', replace_match, text)

# --- Dependency Injection (초기화) ---
if 'services' not in st.session_state:
    st.session_state.services = {
        'learn_db': LearningRepo(),
    }
    st.session_state.viewing_material = None

# 서비스 단축어
svc = st.session_state.services

# --- 페이지별 함수 (간략화) ---

def page_history():
    st.title("📂 학습 콘텐츠 목록")
    
    # 1. 페이지 상태 초기화
    if 'history_page' not in st.session_state:
        st.session_state.history_page = 1
    PAGE_SIZE = 50
    # 2. 전체 데이터 수 및 총 페이지 계산
    total_count = svc['learn_db'].count_materials()
    total_pages = math.ceil(total_count / PAGE_SIZE)
    # 데이터가 하나도 없을 경우 예외 처리
    if total_pages == 0: total_pages = 1
    # 현재 페이지가 범위를 벗어나지 않게 조정 (삭제 등으로 페이지 줄어들 경우)
    if st.session_state.history_page > total_pages:
        st.session_state.history_page = total_pages
    # 3. 현재 페이지 데이터 가져오기
    current_page = st.session_state.history_page
    items = svc['learn_db'].get_materials(page=current_page, page_size=PAGE_SIZE)
    if not items and total_count == 0:
        st.info("저장된 학습 자료가 없습니다.")
        return
    
    # --- 헤더 표시 ---
    # [날짜, 제목, 오디오현황, 열기버튼, 삭제버튼] 비율 설정
    header_cols = st.columns([1.5, 4, 2.5, 1, 1])
    header_cols[0].markdown("**📅 날짜**")
    header_cols[1].markdown("**제목**")
    header_cols[2].markdown("**🎧 오디오**")
    header_cols[3].markdown("**이동**")
    header_cols[4].markdown("**-**")
    
    st.markdown("---")

    # --- 리스트 반복 출력 ---
    for item in items:
        # 각 행의 레이아웃 (헤더와 비율 동일하게 유지)
        row = st.columns([1.5, 4, 2.5, 1, 1])
        
        # 1. 날짜
        row[0].write(item['created_at'].strftime("%Y-%m-%d"))
        
        # 2. 제목 (너무 길면 자르기)
        title_text = item['title']
        if len(title_text) > 70:
            title_text = title_text[:70] + "..."
        row[1].write(title_text)
        
        # 3. 오디오 보유 현황 (아이콘으로 표시)
        audio_status = []
        if item.get('audio_vocab_lecture'): audio_status.append("✅어휘")
        if item.get('audio_summary'): audio_status.append("✅요약")
        if item.get('audio_summary_bi'): audio_status.append("✅번역")
        if item.get('audio_podcast'): audio_status.append("✅팟캐")
        if audio_status:
            row[2].caption(" ".join(audio_status))
        else:
            row[2].caption("-")

        # 4. 바로가기 (열기) 버튼
        # key를 유니크하게 설정해야 함 (open_ + ID)
        if row[3].button("👉 학습", key=f"open_{item['id']}"):
            st.session_state.viewing_material = item
            st.session_state.menu = "4. 콘텐츠 보기" # 메뉴 이동
            st.rerun()

        # 행 구분선
        st.divider()

def page_view_content():
    data = st.session_state.viewing_material
    if not data: return st.warning("선택된 자료 없음")
    st.title(data['title'])
    st.markdown("---")

    # 헬퍼 함수: 오디오 생성 -> 클라우드 업로드 -> DB URL 저장을 처리
    def handle_audio_generation(material_id, field_name, text, speed=0.9, is_podcast=False):
        with st.spinner("오디오 생성 및 클라우드 업로드 중..."):
            # 1. 오디오 생성 (TTS)
            if is_podcast:
                audio_bytes, err = svc['tts'].create_podcast_audio(text, speed)
            else:
                audio_bytes, err = svc['tts'].create_summary_audio(text, speed)
            
            if not audio_bytes:
                st.error(f"오류: {err}")
                return None

            # 2. 클라우드 업로드 (파일 이름: id_field.mp3)
            filename = f"{material_id}_{field_name}.mp3"
            audio_url = svc['storage'].upload_file(audio_bytes, filename)
            
            if not audio_url:
                st.error("클라우드 업로드 실패 (스토리지 설정을 확인하세요)")
                return None

            # 3. DB 업데이트 (URL 저장)
            svc['learn_db'].update_audio(material_id, field_name, audio_url)
            return audio_url

    # c1, c2, c3, c4 = st.columns(4)
    # with c1:
    # with c2:

    # --- 메인 탭 콘텐츠 ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "**1. 어휘 학습**", 
        "**2. 듣기(빈칸쓰기)**", 
        "**3. 번역 듣기**", 
        "**4. 다시 듣기**", 
        "**5. 팟캐스트**", 
        "**6. 퀴즈**", 
        "**7. 원문**"
    ])

    with tab1:
        st.subheader("🎧 어휘 설명 듣기")
        if not data.get('audio_vocab_lecture'):
            if st.button("🔊 어휘 설명 오디오 생성", key="tts_lec"):
                # audio, _ = svc['tts'].create_summary_audio(data.get('vocab_lecture', ''), speed=1.0)
                # if audio:
                #     data['audio_vocab_lecture'] = audio
                #     svc['learn_db'].update_audio(data['id'], 'audio_vocab_lecture', audio)
                #     st.rerun()
                url = handle_audio_generation(data['id'], 'audio_vocab_lecture', data.get('vocab_lecture', ''), 1.0)
                if url:
                    data['audio_vocab_lecture'] = url
                    st.session_state.viewing_material = data
                    st.rerun()
        else:
            st.audio(data['audio_vocab_lecture'])

        # st.markdown("### 주요 단어와 표현")
        st.markdown(data['vocab'])
        # st.markdown(data['vocab_lecture'])

    with tab2:
        st.subheader("🎧 오디오를 들으며 빈 칸을 채워보세요")
        if not data.get('audio_summary'):
            if st.button("🔊 뉴스요약 오디오 생성", key=f"tts_sum_{data['id']}"):
                # with st.spinner("생성 중..."):
                #     audio, err = svc['tts'].create_summary_audio(data['summary'], speed=0.85)
                #     if audio:
                #         data['audio_summary'] = audio
                #         # [DB 업데이트] 오디오 데이터 저장
                #         svc['learn_db'].update_audio(data['id'], 'audio_summary', audio)
                #         st.session_state.viewing_material = data # 세션 갱신
                #         st.rerun()
                #     else:
                #         st.error(f"오류: {err}")
                url = handle_audio_generation(data['id'], 'audio_summary', data['summary'], 0.85)
                if url:
                    data['audio_summary'] = url
                    st.session_state.viewing_material = data
                    st.rerun()
        else:
            st.audio(data['audio_summary'], format="audio/mp3")


        # st.markdown("### 오디오를 들으며 빈 칸을 채워보세요")
        dynamic_blank_text = make_blanks(data['summary'], ratio=0.5)
        st.markdown(f"""
        <div style="font-size:1.1rem; line-height:2.0; background-color:#f9f9f920; padding:20px; border-radius:10px;">
        {dynamic_blank_text.replace(chr(10), "<br>")}
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        st.subheader("🎧 번역을 듣고 완전히 이해하세요")
        if not data.get('audio_summary_bi'):
            if st.button("🔊 한영 교차 오디오 생성", key="tts_bi"):
                # audio, _ = svc['tts'].create_summary_audio(data.get('summary_bi', ''), speed=1.0)
                # if audio:
                #     data['audio_summary_bi'] = audio
                #     svc['learn_db'].update_audio(data['id'], 'audio_summary_bi', audio)
                #     st.rerun()
                url = handle_audio_generation(data['id'], 'audio_summary_bi', data.get('summary_bi', ''), 1.0)
                if url:
                    data['audio_summary_bi'] = url
                    st.session_state.viewing_material = data
                    st.rerun()                    
        else:
            st.audio(data['audio_summary_bi'])


        col_eng, col_kor = st.columns(2)
        with col_eng:
            st.info(f"**English**\n\n{data['summary']}")
        with col_kor:
            st.success(f"**English & Korean**\n\n{data['summary_bi'].replace('\n', '\n\n')}")

    with tab4:
        st.subheader("🎧 보지 말고 들으세요. 따라 말하세요")
        # 이미 생성된 요약 오디오(URL)를 공유해서 사용
        if not data.get('audio_summary'):
             st.info("Tab 1에서 오디오를 먼저 생성해주세요.")
        else:
            st.audio(data['audio_summary'], format="audio/mp3")
            
    with tab5:
        st.subheader("🎧 팟캐스트 대화를 들어보세요")
        if not data.get('audio_podcast'):
            if st.button("🎙️ 팟캐스트 오디오 생성", key=f"tts_pod_{data['id']}"):
                # with st.spinner("AI 성우(2인) 녹음 중... (40-60초)"):
                #     audio, err = svc['tts'].create_podcast_audio(data['podcast'], speed=0.9)
                #     if audio:
                #         data['audio_podcast'] = audio
                #         svc['learn_db'].update_audio(data['id'], 'audio_podcast', audio)
                #         st.session_state.viewing_material = data
                #         st.rerun()
                #     else:
                #         st.error(f"오류: {err}")
                url = handle_audio_generation(data['id'], 'audio_podcast', data['podcast'], 0.9, is_podcast=True)
                if url:
                    data['audio_podcast'] = url
                    st.session_state.viewing_material = data
                    st.rerun()
        else:
            st.audio(data['audio_podcast'], format="audio/mp3")

        # st.markdown("### 대본")
        st.markdown(f"""
        <div class="script-box">
        {data['podcast'].replace(chr(10), "<br>")}
        </div>
        """, unsafe_allow_html=True)

    with tab6:
        st.subheader("문제를 풀어봅시다")

        quizzes = data.get('quiz', [])
        # 데이터가 없거나 형식이 리스트가 아닐 경우(예전 데이터) 예외처리
        if not quizzes or not isinstance(quizzes, list):
            st.info("퀴즈 데이터가 없거나 호환되지 않는 형식입니다.")
        else:
            # 퀴즈 루프
            for idx, q in enumerate(quizzes):
                # 각 문제마다 구분을 위한 컨테이너
                with st.container():
                    st.divider()
                    st.markdown(f"**Q{idx+1}. {q['question']}**")
                    # 1) 객관식 (Multiple Choice)
                    if q['type'] == 'multiple_choice':
                        # 라디오 버튼으로 선택지 표시. 유니크한 key로 상태 관리
                        user_answer = st.radio(
                            "정답을 선택하세요:", 
                            q['options'], 
                            key=f"quiz_{data['id']}_{idx}",
                            index=None # 초기 선택 없음
                        )
                        # 정답 확인 버튼
                        if st.button(f"정답 확인 (Q{idx+1})", key=f"btn_{data['id']}_{idx}"):
                            if user_answer:
                                # 정답 비교 로직 (간단하게 문자열 포함 여부 등으로 체크 가능)
                                # 예: "A)" 로 시작하는지 비교
                                if user_answer.startswith(q['answer'][:3]): 
                                    st.success(f"Correct! 🙆‍♂️\n\n**해설:** {q['explanation']}")
                                else:
                                    st.error("Try again! 🙅‍♂️")
                            else:
                                st.warning("보기를 선택해주세요.")
                    # 2) 주관식 (Short Answer)
                    elif q['type'] == 'short_answer':
                        user_input = st.text_input(
                            "답변을 입력해보세요:", 
                            key=f"quiz_{data['id']}_{idx}"
                        )
                        # 정답 확인 (Expander로 숨김)
                        with st.expander(f"정답 및 해설 확인 (Q{idx+1})"):
                            if user_input:
                                st.caption(f"내 답변: {user_input}")
                            st.markdown(f"**모범 답안:** {q['answer']}")
                            st.info(f"**해설:** {q['explanation']}")

    with tab7:
        st.subheader("기사 원문을 읽어보세요")
        for article in data['articles']:
            with st.expander(f"{article['source']} - {article['title']}"):
                st.write(article.get('full_text', ''))


# --- 메인 ---
def main():

    # 1. 메뉴 이동을 처리할 콜백 함수 정의
    def update_menu(new_menu):
        st.session_state.menu = new_menu

    # 전역에 적용되는 CSS 스타일
    # 전역에 적용되는 CSS 스타일
    st.markdown("""
    <style>
    html, body, p, li, div, .stMarkdown, .stAlert p, .stAlert li, .stAlert div {
        line-height: 2.0;
    }
    /* 작은 캡션이나 부가 설명 텍스트도 조금 키움 */
    .stCaption {
        font-size: 0.95rem !important;
    }
    /* 탭 메뉴들이 들어있는 컨테이너 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px; /* 탭 사이 간격 */
    }
    /* 선택되지 않은 기본 탭 스타일 */
    .stTabs [data-baseweb="tab"] {
        height: 60px; /* 탭 높이 확대 */
        white-space: pre-wrap;
        border-radius: 8px 8px 0px 0px; /* 위쪽 둥근 모서리 */
        gap: 2px;
        padding-top: 10px;
        padding-bottom: 10px;
        padding-left: 20px;
        padding-right: 20px;
        border: 1px solid #ddd;
        border-bottom: none;
    }
    /* 탭 안의 텍스트 폰트 설정 */
    .stTabs [data-baseweb="tab"] div p {
        font-size: 1.1rem !important; /* 탭 글자 크기 키움 */
        font-weight: 700;
    }
    /* 선택된(활성화된) 탭 스타일 */
    .stTabs [aria-selected="true"] {
        border-top: 4px solid #ff4b4b !important; /* 상단에 포인트 컬러 */
        border-left: 1px solid #ddd;
        border-right: 1px solid #ddd;
        /* color: #ff4b4b !important; /* 글자색 포인트 컬러 */
        box-shadow: 0 -5px 5px -5px rgba(0,0,0,0.1); /* 살짝 그림자 */
    }
    
    /* 링크 스타일: 기본 텍스트 색상 상속(inherit) 및 밑줄 제거 */
    a.custom-link {
        color: inherit !important;
        text-decoration: none;
        font-weight: 600; /* 약간 굵게 */
    }
    /* 마우스 올렸을 때만 밑줄 및 색상 변화 (선택사항) */
    a.custom-link:hover {
        text-decoration: underline;
        color: #ff4b4b !important; /* 포인트 컬러 (빨강) */
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.header("영어교재+팟캐스트 생성기")
        menu_items = {
            "3. 콘텐츠 목록": "page_history",
            "4. 콘텐츠 보기": "page_view_content"
        }
        # 초기 메뉴 상태 설정
        if 'menu' not in st.session_state:
            st.session_state.menu = "3. 콘텐츠 목록"

        # 메뉴 버튼 렌더링
        for label, page_func_name in menu_items.items():
            # 현재 선택된 메뉴는 다르게 표시 (primary 버튼으로 강조)
            btn_type = "primary" if label == st.session_state.menu else "secondary"
            
            # if st.button(label, key=f"menu_btn_{label}", type=btn_type, use_container_width=True):
            #     st.session_state.menu = label
            #     st.rerun() # 메뉴 상태가 바뀌면 화면을 갱신합니다.
            # [수정] if st.button(...) 대신 on_click 파라미터 사용: 버튼 클릭 시 update_menu 함수가 먼저 실행되어 menu 상태가 바뀐 채로 화면이 다시 그려집니다 (st.rerun 불필요).
            st.button(
                label, 
                key=f"menu_btn_{label}", 
                type=btn_type, 
                use_container_width=True,
                on_click=update_menu,  # 클릭 시 실행할 함수 지정
                args=(label,)          # 함수에 전달할 인자 (메뉴 이름)
            )
    
    # 메뉴 라우팅
    menu = st.session_state.menu
    if "3." in menu: page_history()
    elif "4." in menu: page_view_content()

if __name__ == "__main__":
    main()

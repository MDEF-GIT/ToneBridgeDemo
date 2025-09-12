#!/bin/bash

# ToneBridge 프로젝트 클린업 스크립트
# .gitignore 패턴 기반으로 불필요한 파일들을 안전하게 정리합니다

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🧹 ToneBridge 프로젝트 클린업 스크립트${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# 현재 디렉토리 확인
if [[ ! -f "replit.md" ]] || [[ ! -d "backend" ]] || [[ ! -d "frontend" ]]; then
    echo -e "${RED}❌ 오류: ToneBridge 프로젝트 루트 디렉토리에서 실행해주세요${NC}"
    echo -e "${YELLOW}   replit.md, backend, frontend 디렉토리가 있는 위치에서 실행하세요${NC}"
    exit 1
fi

# 안전 확인
echo -e "${YELLOW}⚠️  이 스크립트는 다음 파일들을 삭제합니다:${NC}"
echo "   • Python 캐시 파일들 (__pycache__, *.pyc)"
echo "   • 임시 파일들 (*.tmp, *.temp, temp_*)"
echo "   • 백업 파일들 (*.bak, *.backup, *.orig)"
echo "   • 로그 파일들 (참조 파일 제외)"
echo "   • 시스템 파일들 (.DS_Store, Thumbs.db)"
echo
echo -e "${GREEN}✅ 보존되는 파일들:${NC}"
echo "   • 모든 소스 코드 (.py, .ts, .tsx, .js)"
echo "   • 설정 파일들 (requirements.txt, package.json 등)"
echo "   • 참조 오디오 파일들 (.wav, .TextGrid)"
echo "   • 프로덕션 빌드 및 의존성 패키지"
echo

read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ 작업이 취소되었습니다${NC}"
    exit 1
fi

# 정리 시작
echo -e "${BLUE}🚀 프로젝트 정리 시작...${NC}"
echo

# 1. Python 캐시 파일 정리
echo -e "${PURPLE}📂 Python 캐시 파일 정리 중...${NC}"
DELETED_PYCACHE=$(find . -name "__pycache__" -type d 2>/dev/null | wc -l)
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

DELETED_PYC=$(find . -name "*.pyc" -type f 2>/dev/null | wc -l)
find . -name "*.pyc" -type f -delete 2>/dev/null || true

DELETED_PYO=$(find . -name "*.pyo" -type f 2>/dev/null | wc -l)
find . -name "*.pyo" -type f -delete 2>/dev/null || true

echo -e "   ✅ __pycache__ 디렉토리: ${DELETED_PYCACHE}개 삭제"
echo -e "   ✅ *.pyc 파일: ${DELETED_PYC}개 삭제"
echo -e "   ✅ *.pyo 파일: ${DELETED_PYO}개 삭제"

# 2. 임시 파일 정리
echo -e "${PURPLE}📂 임시 파일 정리 중...${NC}"
DELETED_TMP=$(find . -name "*.tmp" -type f 2>/dev/null | wc -l)
find . -name "*.tmp" -type f -delete 2>/dev/null || true

DELETED_TEMP=$(find . -name "*.temp" -type f 2>/dev/null | wc -l)
find . -name "*.temp" -type f -delete 2>/dev/null || true

DELETED_TEMP_PREFIX=$(find . -name "temp_*" -type f 2>/dev/null | wc -l)
find . -name "temp_*" -type f -delete 2>/dev/null || true

echo -e "   ✅ *.tmp 파일: ${DELETED_TMP}개 삭제"
echo -e "   ✅ *.temp 파일: ${DELETED_TEMP}개 삭제"
echo -e "   ✅ temp_* 파일: ${DELETED_TEMP_PREFIX}개 삭제"

# 3. 백업 파일 정리
echo -e "${PURPLE}📂 백업 파일 정리 중...${NC}"
DELETED_BAK=$(find . -name "*.bak" -type f 2>/dev/null | wc -l)
find . -name "*.bak" -type f -delete 2>/dev/null || true

DELETED_BACKUP=$(find . -name "*.backup" -type f 2>/dev/null | wc -l)
find . -name "*.backup" -type f -delete 2>/dev/null || true

DELETED_ORIG=$(find . -name "*.orig" -type f 2>/dev/null | wc -l)
find . -name "*.orig" -type f -delete 2>/dev/null || true

DELETED_SAVE=$(find . -name "*.save" -type f 2>/dev/null | wc -l)
find . -name "*.save" -type f -delete 2>/dev/null || true

echo -e "   ✅ *.bak 파일: ${DELETED_BAK}개 삭제"
echo -e "   ✅ *.backup 파일: ${DELETED_BACKUP}개 삭제"
echo -e "   ✅ *.orig 파일: ${DELETED_ORIG}개 삭제"
echo -e "   ✅ *.save 파일: ${DELETED_SAVE}개 삭제"

# 4. 로그 파일 정리 (참조 파일은 보존)
echo -e "${PURPLE}📂 로그 파일 정리 중...${NC}"
DELETED_LOGS=$(find . -name "*.log" -not -path "./backend/static/reference_files/*" -type f 2>/dev/null | wc -l)
find . -name "*.log" -not -path "./backend/static/reference_files/*" -type f -delete 2>/dev/null || true

echo -e "   ✅ 로그 파일: ${DELETED_LOGS}개 삭제 (참조 파일 보존됨)"

# 5. 시스템 파일 정리
echo -e "${PURPLE}📂 시스템 파일 정리 중...${NC}"
DELETED_DS_STORE=$(find . -name ".DS_Store" -type f 2>/dev/null | wc -l)
find . -name ".DS_Store" -type f -delete 2>/dev/null || true

DELETED_THUMBS=$(find . -name "Thumbs.db" -type f 2>/dev/null | wc -l)
find . -name "Thumbs.db" -type f -delete 2>/dev/null || true

DELETED_DESKTOP_INI=$(find . -name "Desktop.ini" -type f 2>/dev/null | wc -l)
find . -name "Desktop.ini" -type f -delete 2>/dev/null || true

echo -e "   ✅ .DS_Store 파일: ${DELETED_DS_STORE}개 삭제"
echo -e "   ✅ Thumbs.db 파일: ${DELETED_THUMBS}개 삭제"
echo -e "   ✅ Desktop.ini 파일: ${DELETED_DESKTOP_INI}개 삭제"

# 6. 특정 디렉토리 정리
echo -e "${PURPLE}📂 특정 디렉토리 정리 중...${NC}"

# backend/temp 디렉토리 정리
if [[ -d "backend/temp" ]]; then
    TEMP_FILES=$(find backend/temp -type f 2>/dev/null | wc -l)
    find backend/temp -type f -delete 2>/dev/null || true
    echo -e "   ✅ backend/temp: ${TEMP_FILES}개 파일 정리"
fi

# backend/static/uploads 임시 파일 정리
if [[ -d "backend/static/uploads" ]]; then
    UPLOAD_TEMP=$(find backend/static/uploads -name "*.tmp" -o -name "temp_*" -type f 2>/dev/null | wc -l)
    find backend/static/uploads -name "*.tmp" -type f -delete 2>/dev/null || true
    find backend/static/uploads -name "temp_*" -type f -delete 2>/dev/null || true
    echo -e "   ✅ uploads 임시 파일: ${UPLOAD_TEMP}개 정리"
fi

# 7. 정리 완료 후 상태 확인
echo
echo -e "${BLUE}📊 정리 후 상태 확인...${NC}"

# 남은 파일들 확인
REMAINING_PYCACHE=$(find . -name "__pycache__" -type d 2>/dev/null | wc -l)
REMAINING_PYC=$(find . -name "*.pyc" -type f 2>/dev/null | wc -l)
REMAINING_TMP=$(find . -name "*.tmp" -o -name "*.temp" -type f 2>/dev/null | wc -l)
REMAINING_BAK=$(find . -name "*.bak" -o -name "*.backup" -type f 2>/dev/null | wc -l)

echo -e "   📈 Python 캐시: ${REMAINING_PYCACHE}개 __pycache__, ${REMAINING_PYC}개 *.pyc 파일 남음"
echo -e "   📈 임시 파일: ${REMAINING_TMP}개 남음"
echo -e "   📈 백업 파일: ${REMAINING_BAK}개 남음"

# 중요 파일 보존 확인
echo
echo -e "${GREEN}🛡️  보존된 중요 파일들:${NC}"

AUDIO_FILES=$(find ./backend/static/reference_files -name "*.wav" 2>/dev/null | wc -l)
TEXTGRID_FILES=$(find ./backend/static/reference_files -name "*.TextGrid" 2>/dev/null | wc -l)
PYTHON_FILES=$(find . -name "*.py" -not -path "./.pythonlibs/*" -not -path "./.cache/*" 2>/dev/null | wc -l)
TS_FILES=$(find . -name "*.ts" -o -name "*.tsx" -o -name "*.jsx" 2>/dev/null | wc -l)

echo -e "   🎵 참조 오디오 파일: ${AUDIO_FILES}개"
echo -e "   📊 TextGrid 파일: ${TEXTGRID_FILES}개"
echo -e "   🐍 Python 파일: ${PYTHON_FILES}개"
echo -e "   ⚛️  TypeScript/React 파일: ${TS_FILES}개"

# 설정 파일 확인
echo -e "   ⚙️  설정 파일들:"
[[ -f "backend/requirements.txt" ]] && echo -e "      ✅ requirements.txt" || echo -e "      ❌ requirements.txt 누락"
[[ -f "backend/requirement___.txt" ]] && echo -e "      ✅ requirement___.txt" || echo -e "      ❌ requirement___.txt 누락"
[[ -f "frontend/package.json" ]] && echo -e "      ✅ package.json" || echo -e "      ❌ package.json 누락"
[[ -f ".gitignore" ]] && echo -e "      ✅ .gitignore" || echo -e "      ❌ .gitignore 누락"
[[ -f "replit.md" ]] && echo -e "      ✅ replit.md" || echo -e "      ❌ replit.md 누락"

# 총 삭제된 파일 수 계산
TOTAL_DELETED=$((DELETED_PYCACHE + DELETED_PYC + DELETED_PYO + DELETED_TMP + DELETED_TEMP + DELETED_TEMP_PREFIX + DELETED_BAK + DELETED_BACKUP + DELETED_ORIG + DELETED_SAVE + DELETED_LOGS + DELETED_DS_STORE + DELETED_THUMBS + DELETED_DESKTOP_INI))

# 완료 메시지
echo
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ 프로젝트 클린업 완료!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 총 ${TOTAL_DELETED}개 파일/디렉토리가 정리되었습니다${NC}"
echo
echo -e "${YELLOW}💡 다음번 정리는 다음 명령어로 실행하세요:${NC}"
echo -e "${YELLOW}   ./clean_project.sh${NC}"
echo
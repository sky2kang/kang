# 키움증권 OpenAPI+ 자동매매 프로그램

Python + PyQt5 기반 키움증권 자동매매 시스템입니다.

## 시스템 요구사항

| 항목 | 내용 |
|------|------|
| OS | **Windows 10/11 64bit** (키움 OpenAPI+ 는 Windows 전용) |
| Python | 3.8 ~ 3.11 (32bit 또는 64bit) |
| 키움 계좌 | 키움증권 계좌 개설 필요 |

---

## 설치 순서

### 1. 키움증권 OpenAPI+ 설치
1. [키움증권 홈페이지](https://www.kiwoom.com) → 트레이딩 → Open API+ 메뉴
2. `KHOpenAPI.exe` 다운로드 및 설치
3. **모의투자 신청** (홈페이지 → 트레이딩 → 모의투자 신청)

### 2. Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 계좌번호 등 실제 값 입력
```

### 4. 실행
```bash
# 모의투자 (기본) - MA 골든크로스 전략
python main.py

# RSI 전략으로 실행
python main.py --strategy rsi

# 조건검색식 기반 매매 (HTS에서 만든 조건식 이름 지정)
python main.py --mode condition --condition "급등주포착"

# 실거래 모드 (주의!)
python main.py --simul false
```

---

## 조건검색식 기반 자동매매 (실전형) ⭐

HTS(영웅문)에서 직접 만든 **조건검색식**을 실시간으로 받아 매매하는 방식입니다.
국내 자동매매에서 가장 많이 쓰이는 실전 패턴입니다.

### 동작 방식
| 이벤트 | 동작 |
|--------|------|
| 종목이 조건식에 **편입(I)** | 자동 **매수** |
| 보유 종목이 조건식에서 **이탈(D)** | 자동 **매도** |
| 손절(-5%) / 익절(+10%) | 3분마다 보유종목 점검 후 매도 |

### 사용 순서
1. **영웅문HTS [0150] 조건검색** 화면에서 원하는 조건식 작성
2. 조건식을 **"내 조건식"으로 저장** (예: `급등주포착`)
3. 저장한 조건식 이름으로 실행:
   ```bash
   python main.py --mode condition --condition "급등주포착"
   ```

> 조건식은 서버에 저장되어야 API가 불러올 수 있습니다.
> 로컬에만 있는 조건식은 인식되지 않으니 반드시 **저장** 하세요.

---

## 프로젝트 구조

```
kang/
├── main.py                  # 메인 실행 진입점
├── requirements.txt
├── .env.example             # 환경변수 예시
│
├── config/
│   └── settings.py          # 전역 설정 (계좌, 매매 한도, 시간 등)
│
├── core/
│   ├── kiwoom.py            # 키움 OpenAPI+ 래퍼 클래스 (조건검색 포함)
│   ├── market_data.py       # 시세·계좌 조회 (TR 조회)
│   ├── trader.py            # 주문 실행 + 리스크 관리
│   └── condition_trader.py  # 조건검색식 기반 실시간 매매
│
├── strategy/
│   ├── base_strategy.py     # 전략 추상 기본 클래스
│   ├── ma_strategy.py       # 이동평균 골든/데드크로스 전략
│   └── rsi_strategy.py      # RSI 과매수/과매도 전략
│
├── utils/
│   ├── logger.py            # 로테이팅 파일 로거
│   └── db.py                # SQLite 매매 기록 DB
│
├── logs/                    # 실행 로그 저장
└── data/
    └── trades.db            # 매매 기록 SQLite DB
```

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 자동 로그인 | 키움 OpenAPI+ 팝업 로그인 |
| 시세 조회 | 현재가, 일봉/분봉 OHLCV |
| 계좌 조회 | 잔고, 보유종목, 수익률 |
| 매수 주문 | 시장가 자동 매수 |
| 매도 주문 | 손절/익절/전략 신호 시 자동 매도 |
| 리스크 관리 | 최대 보유 종목수, 손절(-5%), 익절(+10%) |
| 기록 저장 | SQLite에 주문 이력 + 일일 결산 저장 |

---

## 매매 전략

### MA 골든크로스 (기본)
- **매수**: 5일 이동평균이 20일 이동평균을 상향 돌파
- **매도**: 데드크로스 또는 손절/익절 조건

### RSI 전략
- **매수**: RSI가 30 이하에서 30 이상으로 반등
- **매도**: RSI 70 이상 또는 손절/익절 조건

### 커스텀 전략 추가
`strategy/base_strategy.py`의 `BaseStrategy`를 상속 후 `should_buy()`, `should_sell()` 구현

---

## 리스크 관리 설정 (`.env`)

```
STOP_LOSS_RATE=-0.05      # 손절 기준 (-5%)
TAKE_PROFIT_RATE=0.10     # 익절 기준 (+10%)
MAX_BUY_AMOUNT=1000000    # 1회 최대 매수금액 1,000,000원
MAX_STOCK_COUNT=5         # 최대 동시 보유 종목수
```

---

## 주의사항

> **실거래 모드 전 반드시 모의투자로 충분히 테스트하세요.**
> 자동매매에 의한 손실에 대한 책임은 사용자 본인에게 있습니다.

- 키움 OpenAPI+는 **1초 5회, 1분 100회** TR 요청 제한이 있습니다
- 장 운영 시간: 09:00 ~ 15:30 (기본 매매 시간: 09:05 ~ 15:20)
- 모의투자와 실거래는 서버가 다르므로 `.env`의 `KIWOOM_SIMUL` 값을 반드시 확인하세요

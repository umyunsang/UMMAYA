# KMA APIHub Service Scope

Snapshot date: 2026-05-26 KST. Source: official KMA APIHub category detail pages under `https://apihub.kma.go.kr/apiList.do`.

This document is the routing and wrapping scope map for UMMAYA. It covers the main APIHub catalog pages (`apiList.do`) plus the currently observed `typ02/openApi` operation set. `specialApiList.do` is a separate industrial-special surface and is tracked as a boundary, not merged into the main catalog below.

## Active Routing Rules

| Citizen query | Preferred UMMAYA route | Notes |
|---|---|---|
| Airport aviation weather, METAR, SPECI | `kma_apihub_url_air_metar_decoded` for approved decoded METAR; structured `AmmIwxxmService/getMetar` stays cataloged-disabled after `resultCode=01` probes | Use ICAO codes when a structured aviation operation supports them: RKSS Gimpo, RKPK Gimhae. |
| AMOS runway-area minute observations | `kma_apihub_url_air_amos_minute` | Official AMOS station list includes Gimpo `110`; Gimhae is not listed on the AMOS page. |
| Airport departure forecast / TAF / SIGMET / AIRMET | Cataloged `typ02/openApi` aviation operations, currently `approval_pending` until utilization approval and direct curl proof are captured | Do not expose as active tools before approval. |
| High-resolution analyzed values / objective analysis / 분석자료 | `kma_apihub_url_high_resolution_grid_point` or `kma_apihub_url_aws_objective_analysis_grid` | These are KMA-analyzed products and can support interpretation, but they do not replace official aviation METAR/AMOS wording. |
| Analyzed surface or auxiliary weather chart | `WthrChartInfoService/*` cataloged-disabled plus `kma_apihub_url_analysis_weather_chart_image` for the typ07 image family | Direct probes on 2026-05-26 returned `resultCode=99` for the structured chart endpoints. |
| Korean address current weather / forecast | Specialized KMA current/forecast adapters (`kma_current_observation`, `kma_ultra_short_term_forecast`, `kma_short_term_forecast`, `kma_forecast_fetch`) | Resolve location first; do not use aviation tools for ordinary neighborhood weather. |
| Satellite/radar/earthquake/typhoon/world-weather products | Structured APIHub adapters when active, otherwise catalog entry with approval/upstream status | Fail closed on 401/403/99/DB_ERROR; no fabricated weather values. |

## Catalog Totals

- Main service pages inspected: 55
- Current `typ02/openApi` operations observed: 145
- Structured operations registered active in UMMAYA after fail-closed pruning: 77
- Structured operations retained but inactive: 68 (`approval_pending`, `upstream_unavailable`, or `retired`)
- Non-structured URL operations registered for this aviation/analyzed-data pass: 5

## Service Scope Table

| seqApi | Category | seqApiSub | API | Scope cue | Elements cue | Period / cycle | Endpoint families | typ02 operations observed |
|---:|---|---:|---|---|---|---|---|---:|
| 2 | 지상관측 | 238 | 종관기상관측(ASOS) | 종관기상관측이란 정해진 시각의 대기 상태를 파악하기 위해 모든 관측소에서 같은 시각에 실시하는 지상관측을 말합니다. 시정, 구름, 증발량, 일기현상 등 일부 목측 요소를 제외하고 종관기상관측장비(... | - | 1904년 4월 ~ 현재(지점별 상이함) / 분, 시간, 일, 월, 연 자료 | typ01, typ02/openApi, typ03 | 12 |
| 2 | 지상관측 | 239 | 방재기상관측(AWS) | 방재기상관측이란 지진 · 태풍 · 홍수 · 가뭄 등 기상현상에 따른 자연재해를 막기 위해 실시하는 지상관측을 말합니다. 관측 공백 해소 및 국지적인 기상 현상을 파악하기 위하여 전국 약 510여 ... | - | 1997년 1월 ~ 현재(지점별 상이함) / 분, 시간, 일, 월, 연 자료 | typ01, typ02/openApi, typ03 | 8 |
| 2 | 지상관측 | 1131 | 기후통계 | 기후통계란 기상요소를 대상으로 한 통계입니다. 어느 기간 전체의 기상상태를 알기 위해서 해당 기간의 기상요소 관측값(또는 통계값) 전체에 대하여 합계, 평균, 누적값, 극값 등의 통계를 산출한 기... | 기압, 바람, 기온, 이슬점온도, 지면온도, 초상온도, 지중온도, 습도, 증기압, 구름, 시정, 강수량, 적설, 신적설, 일사, 일조, 증발량, 황사, 안개 | 1904년 ~ / 일, 월, 연 | typ01 | 0 |
| 2 | 지상관측 | 240 | 북한기상관측 | 북한이 세계기상기구(WMO, World Meteorogical Organization)의 기상통신망(GTS)을 통해 보낸 27개 지점의 관측 자료입니다. | - | 1973년 1월 ~ 현재(지점별 상이함) / 시간, 일 자료 | typ01 | 0 |
| 2 | 지상관측 | 243 | 황사관측(PM10) | 황사관측(PM10)는 대기 중에 부유하는 에어로졸 중 직경이 10㎛ 이하인 입자의 농도를 연속 측정합니다. 먼지(황사 포함)가 필터에 침적되고, 동위원소 C-14에서 방출되는 베타선을 필터 여지에... | - | 2003년 4월 ∼ 현재(지점별 상이함) / 분(5분 주기), 시간 자료 | typ01, typ02/openApi | 3 |
| 2 | 지상관측 | 244 | 적설관측 | 적설이란 고체상의 강수(눈, 싸락눈 등)가 지면에 내려 쌓여 있는 수직 깊이를 말합니다. 눈이 관측장소 또는 관측장소 주위의 지면에 반 이상을 덮었을 때를 적설이 있는 것으로 판단합니다. 목측관측... | - | - / 일, 3시간, 6시간, 24시간(관측방법에 따라 상이함) | typ01 | 0 |
| 2 | 지상관측 | 245 | 자외선관측 | 자외선 복사는 일반적으로 자외선A(315~400nm), 자외선B(280~315nm), 자외선C(100~280nm)로 나뉘며, 이 중 자외선A와 자외선B는 오존층에 일부가 흡수되고 그 나머지가 지표... | - | 1994년 1월 ~ 현재 / 일, 월, 연 자료 | typ01 | 0 |
| 2 | 지상관측 | 248 | AWS 객관분석 | - | - | - / - | typ01 | 0 |
| 2 | 지상관측 | 926 | 계절관측 | 계절관측 데이터는 계절의 빠르고 늦음의 지역적인 차이 등을 합리적으로 관특 및 통계 분석하여 기후변화의 추이를 통괄적으로 파악하기 위해 관측장소에서 관측차가 지정된 식물, 동물, 기후계절 등을 관... | ● 식물계절관측: 개나리, 진달래, 벚나무, 단풍나무 등 / ● 동물계절관측: 제비, 개구리, 나비, 잠자리, 뻐꾸기, 매미 등 / ● 기후계절관측: 눈, 서리, 얼음, 강·하천 결빙 및 해빙 등 | 1904년 ~ 현재(요소별, 지점별 상이함) / 연 자료 | typ01 | 0 |
| 2 | 지상관측 | 317 | 지상관측 지점정보 | - | - | - / - | typ01 | 0 |
| 3 | 해양관측 | 249 | 해양기상부이·파고부이관측 | 해양기상부이는 해수면에서 해양기상현상을 다양한 기상장비로 측정하고, 그 값을 일정한 물리량으로 변환 · 처리한 후에 위성 등 원격통신을 이용하여 관측 자료를 전송합니다. / 파고부이는 해양기상부이... | - | (해양기상부이) 1996년 7월 ~ 현재(지점별 상이함)/ (파고부이) 2009년 1월 ~ 현재(지점별 상이함) / 매시 30분 및 정시(00분), 일 자료 | typ01, typ02/openApi, typ03 | 14 |
| 3 | 해양관측 | 250 | 등표기상관측 | 등표기상관측장비는 등표나 관측탑 등의 해양 구조물에 기상관측장비를 설치하고 수중에는 해상상태를 측정할 수 있는 파고계 등을 설치하여 관측기기에서 측정한 값을 일정한 물리량으로 변환 · 처리한 후에... | - | 2001년 12월 ~ 현재(지점별 상이함) / 시간, 일 자료 | typ01 | 0 |
| 3 | 해양관측 | 251 | 기상1호 | 기상관측선 기상1호는 2011년 5월 30일 취항하였습니다. / 기상1호는 해양에서 고층-해상-해양-대기 환경등을 관측하는 이동기상대 역할을 수행하며, 위험기상 예상 시 관측효과를 극대화할 수 있... | - | 2011년 6월 ~ 현재(관측 요소별 상이함) / 시간, 일 자료 | typ01 | 0 |
| 3 | 해양관측 | 318 | 해양관측 지점정보 | - | - | - / - | typ01 | 0 |
| 4 | 고층관측 | 254 | 레윈존데 | 라디오존데를 기구에 매달아 비양시켜 지상으로부터 30km이상 상공까지 일정한 시간 간격으로 대기상태를 직 · 간접적으로 관측합니다. 관측자료는 무선 송수신장치를 통해 지상으로 전송되고 지상 수신장... | - | 1957년 4월 1일 ~ 현재(지점별 상이함) / 시간 자료 | typ01, typ02/openApi | 6 |
| 4 | 고층관측 | 255 | 연직바람관측 | 연직바람관측장비(Wind Profiler Radar)는 초단파, 극초단파(UHF, 300~3000 ㎒) 전파빔을 상층대기로 송신하여 바람과 함께 이동하는 난류에서 산란되어 오는 전파신호를 수신해 ... | - | 2004년 1월 ~ 현재(지점별 상이함) / 분(10분주기) 자료 | typ01 | 0 |
| 4 | 고층관측 | 319 | 고층관측 지점정보 | - | - | - / - | typ01 | 0 |
| 5 | 레이더 | 265 | 레이더 강수량(HSR) | 지형차폐의 영향이 없는 지상에 가장 가까운 고도각 자료로 추정한 레이더 강우량(HSR: Hybrid Surface Rainfall)으로, 지형에코와 비기상에코 등의 영향을 최소화하여 레이더 강우량... | - | 2016년 ~ 현재 / 분(5분 주기) 자료 | typ01, typ02/openApi | 2 |
| 5 | 레이더 | 266 | 레이더 강수량 | 레이더 강수량은 각각의 레이더 관측소에서 생산된 관측자료를 합성하여 우리나라 전역의 레이더 합성영상자료를 산출하고, 이를 활용하여 우리나라에 영향을 주는 강수의 범위와 이동경향감시 분석 등에 이용... | - | 2016년 ~ 현재 / 분(10분 주기) 자료 | typ04, typ02/openApi, typ03 | 2 |
| 5 | 레이더 | 267 | 레이더 원시자료 | 기상레이더는 전자파를 발사, 대기 중의 물방울에 부딪혀 되돌아오는 반사파를 분석하여 강수의 지역과 세기 등을 관측하는 장비입니다. 주로 집중호우, 우박 등 위험기상과 한반도로 접근하는 태풍을 추적... | - | - 관악산, 오성산, 구덕산, 고산, 강릉: 1998년 ~ 현재 / - 백령도, 진도, 인천공항: 2001년 ~ 현재 / -... / 분(5, 10분 주기) 자료 | typ01, typ04 | 0 |
| 5 | 레이더 | 269 | 레이더 AWS지점별 합성자료값 | 레이더 합성영상 격자자료에서 AWS 지점과 가장 인접한 지점의 값을 추출하여 표출합니다. | - | - / - | typ01 | 0 |
| 5 | 레이더 | 264 | 낙뢰관측 | 발달하는 적란운 구름 내부에 분리 축적된 음전하와 양전하 사이에서 번개현상이 발생하고 구름 하단과 지면 사이에 발생하는 방전 현상을 낙뢰라고 합니다. 기상청 낙뢰관측자료는 전국 21개소 낙뢰관측장... | - | 1988년 1월 ~ 현재(지점별 상이함) / 분(5분 주기) 자료 | typ01, typ03 | 0 |
| 5 | 레이더 | 320 | 레이더 지점정보 | - | - | - / - | typ02/openApi | 1 |
| 6 | 위성 | 271 | 천리안 2A호 | 2018년 12월 5일에 발사된 천리안위성 2A호는 천리안위성 1호의 기상관측 역할을 승계하는 차세대 정지궤도 기상위성으로 기상 및 우주기상 관측임무를 수행합니다. / 천리안위성 2A호는 16개의... | - | 2019년 7월 ∼ 현재 / - 전구/동아시아: 매시 정각부터 10분 간격 / - 한반도: 매시 정각부터 2분 간격 | typ05, typ01, typ02/openApi, typ03 | 20 |
| 6 | 위성 | 270 | 천리안 1호 | 2010년에 발사된 천리안위성(COMS, Communication Ocean and Meteorological Satellite)은 지구적도상공 36,000km 고도, 동경 128.2°에 위치하여... | - | 2011년 4월 ∼ 2020년 3월 / - 북반구: 매시 00, 15, 30, 45분 / - 한반도: 매시 13, 28, 43, 58분 / - 전구: 3시간마다 매... | typ01, typ04 | 0 |
| 7 | 지진/화산 | 273 | 국내·외 지진정보 | 지진정보는 국내에서 규모 2.0 이상인 지진이 발생한 경우 발표한 자료입니다. / 국외지진정보는 구역 내 지역에서 규모 5.0 이상, 해역에 5.5 이상일 경우와 구역 외 지역에서 규모 6.0 이... | - | 2001년 3월 ~ 현재 / 지진 발생시 | typ01, typ02/openApi, typ09 | 2 |
| 7 | 지진/화산 | 274 | 지진해일정보 | 지진해일정보는 지진해일특보 기준에는 미치지 못하나 우리나라에 영향이 예상되거나 지진해일 특보 발표 이후, 주요지점별 지진해일 예측정보 또는 실제 관측된 지진해일 자료 등 추가 정보를 알릴 필요가 ... | - | 2020년 4월 ~ 현재 / 발생시 / ※ 지진해일정보 서비스 이래로 발표된 지진해일정보는 없습니다.(2023. 7. 24. 기준) | typ09, typ02/openApi | 2 |
| 7 | 지진/화산 | 275 | 화산정보 | 화산정보는 한반도 및 그 주변지역 또는 국외에서 발생한 화산현상에 관한 자료입니다. | - | 2010년 7월 ~ 현재 / 발생시 | typ09 | 0 |
| 8 | 태풍 | 276 | 태풍정보 | 태풍 예상정보는 현재 태풍(Tropical Cyclone)의 중심위치, 중심기압, 중심부근 최대풍속, 강풍반경, 폭풍반경, 진행방향, 이동속도를 제공합니다. | - | 현재 진행 중인 태풍에 한하여 제공 / 4, 10, 16, 22시 및 필요 시 수시 발표 | typ01, typ02/openApi | 1 |
| 8 | 태풍 | 277 | 태풍정보(TD) | 태풍정보(TD)는 태풍 사전단계 또는 태풍에서 약화된 뒤에도 우리나라에 영향을 줄 수 있는 열대저압부(Tropical Depression)를 대상으로 중심위치, 예상경로 등의 종합적인 정보를 제공... | - | 2015년 ~ 현재 / 4, 10, 16, 22시 및 필요시 수시 발표 | typ01 | 0 |
| 8 | 태풍 | 1000 | 태풍 베스트트랙 | 태풍예보 상황에서 실황분석 자료로 활용되지 못했던 자료들을 확보하여 보다 정밀하게 재분석된 사후 태풍정보 | 등급, 태풍호수, 년, 월, 일, 시, 경·위도, 중심최대풍속, 중심기압, 강풍(15m/s, 25m/s 이상)반경 장반경·단반경·방향, 태풍이름 | 2015~2022년 / 연 1회 (매년 7월 전년도 자료 업데이트) | typ01 | 0 |
| 9 | 수치모델 | 278 | 수치예보모델 | (전구) 전지구 예보모델(GDAPS, Global Data Assimilation and Prediction System)은 전지구 날씨 예측, 동네예보, 중기예보 등을 목적으로 영국 통합모델(U... | - | (전구) 2011년 5월 ~ 현재 / (지역) 2010년 3월 ~ 현재 / (국지) 2012년 5월 ~ 현재 / 일 4회(00, 06, 12, 18UTC) | typ06, typ02/openApi, typ01 | 8 |
| 9 | 수치모델 | 282 | 초단기예측 | - | - | - / - | typ03 | 0 |
| 9 | 수치모델 | 285 | 수치모델 그래픽 | 수치모델에서 생산된 수치자료의 변수들에 대한 등치선, 등치면 등 그래픽을 제공하며 프로그래밍을 통해 함께 제공한 배경지도, 경위도선과 중첩하여 원하는 일기도를 제작할 수 있습니다. / ※ 일기도 ... | - | - / 일 4회(00, 06, 12, 18UTC) | typ07 | 0 |
| 9 | 수치모델 | 989 | 분석일기도 | 수치분석일기도는 수치예보시스템에서 생산된 수치자료 및 관측자료를 이용하여 기상 변수들에 대한 기호와 등치선 등으로 이루어진 일기도를 뜻하며, 일기예보를 위하여 예보관 및 사용자들에게 제공됩니다. | 지상(3시간), 지상(6시간), 지상기압변화(3시간), 파랑, 폭풍해일, 보조, 고층, 단열선도, 연직시계열, 앙상블 등 | 2004년 1월 ∼ 현재 / ※ 일기도별 생산기간이 상이하며, 이에 따라 보유기간 차이발생 / 일 4회(00, 06, 12, 18UTC) | typ02/openApi | 2 |
| 10 | 예특보 | 286 | 단기예보 | 단기예보란 예보기간과 구역을 시 · 공간적으로 세분화하여 발표하는 예보입니다. 지역별, 시간별 차이로 인한 수요자의 불편을 최소화하기 위해 전국을 5km * 5km 간격의 격자(동서 149(745... | - | 2008년 10월 30일 17:00KST(시행일 기준) ~ 현재 / 2시부터 3시간 간격(일 8회) | typ01, typ02/openApi, typ03 | 7 |
| 10 | 예특보 | 287 | 중기예보 | 중기예보란 예보일로부터 4일(최대5일)에서 10일까지의 기간에 대한 예보를 뜻합니다. 4일(최대5일)에서 7일까지는 오전과 오후로 구분하여 예보하고, 8일에서 10일까지는 일 단위로 구분하여 예보... | - | 2012년 12월 18일 18:00KST(시행일기준) ~ 현재 / (2013년 10월 15일 18:00KST부터 7일 → 1... / 12시간 간격(06, 18시) | typ01, typ02/openApi | 4 |
| 10 | 예특보 | 288 | 기상특보 | 호우, 대설, 폭풍해일 등 10개 기상현상으로 인해 중대한 재해발생이 예상될 때 해당 지역에 대하여 기상특보의 발표 기준에 따라 주의보 및 경보로 구분하여 발표합니다. / 기상특보는 171개 시 ... | - | 2004년 6월 30일 ~ 현재 / 특보 발표시 | typ01, typ03 | 0 |
| 10 | 예특보 | 289 | 영향예보 | 영향예보는 날씨 뿐만 아니라 시간과 장소에 따라 달라지는 날씨의 영향을 고려하여 기상 현상별 위험수준에 따른 분야별 상세 영향정보와 대응요령을 제공합니다. / 이를 통해 유관기관에 실효적 정보를 ... | - | 2019년 6월 ~ 현재 / 발표기준 부합시 일 1회 발표(11시 30분) | typ01 | 0 |
| 10 | 예특보 | 321 | 예·특보 구역정보 | - | - | - / - | typ02/openApi, typ01 | 2 |
| 971 | 융합기상 | 936 | 고해상도 격자자료 | 기상청 및 공공기관(산림청, 농진청 등) 관측자료(AWS, 해양기상부이, 등표)에 지형효과를 반영한 3차원 객관분석 기법을 적용하여 생산한 분석자료입니다. / ※ 해당 자료는 관측자료를 분석하여 ... | - (3차원 분석)기온, 이슬점온도, 습도, 현지기압, 체감온도, 적설, 일신적설, 3시간 신적설, 24시간 신적설 / - (2차원 분석)해면기압, 풍속, 풍향, 강수유무, 강수량(15분, 60분... | - 1997. 1. 1. ~ / ※ 고해상도 격자자료 적설(적설, 일신적설, 3시간신적설, 24시간신적설) 2020. 1. ... / 매정시 기준 5분 간격 / - (1997. 1. 1. ~) 0분, 5분, 10분, 15분, 20분, 25분, 30분, 35분... | typ01 | 0 |
| 971 | 융합기상 | 983 | 에너지 지원 | 신재생에너지 등 신산업 지원을 위해 천리안2A호 데이터와 인공지능기법인 합성곱 인공신경망(CNN)을 활용하여 산출한 일사량 데이터입니다. | - 천리안2A호 인공지능 기반 한반도 전천일사량(MJ/㎡) | - 2019. 7. 25. 00UTC ~ / - 매정시 20분(1시간 간격)/2019. 7. 25. 00UTC ~ 2023. 6. 26. 05UTC / - 매정시 20분... | typ01 | 0 |
| 971 | 융합기상 | 292 | 생활안전 | (생활기상지수) 기상정보와 기상 외적인 요인을 이용하여 국민 일상생활에 활용할 수 있도록 개발된 정보입니다. 동네예보 지점별로 조회가 가능하며 오늘, 내일, 모레의 예측단계를 제공합니다. / / ... | - | - / 일 2회 또는 일 8회(지수별 상이함) / ※ 최근 1일 자료만 조회 가능합니다. | typ02/openApi | 6 |
| 971 | 융합기상 | 293 | 교통안전 | CCTV 기반 도로날씨정보는 고속도로에 설치되어 있는 도로 CCTV 영상을 활용하여 도로경로별 기상정보(안개, 비, 눈)를 생산하여 안전한 도로주행을 위해 제공하는 정보입니다. | - | 2016.12.~현재(고속도로 노선별 보유기간은 상이함) / 실시간 | typ01, typ02/openApi, typ04 | 2 |
| 971 | 융합기상 | 987 | 산업 | - | - | - / - | typ02/openApi, typ08 | 15 |
| 14 | 항공기상 | 257 | 항공기상관측(METAR) | 항공기상관측은 항공기 안전운항에 필요한 기상정보를 생산·제공하기 위하여 공항 내 기상상태를 항공기상관측지침에 의해 측정하는 업무이며, 해당 관측은 당해 공항 내에서 사용하는 보고와 당해 공항 밖으... | - | - / 시간(특정 기준에 해당하는 변화 발생시 특별관측 수시 수행) | typ02/openApi, typ01 | 10 |
| 14 | 항공기상 | 259 | 공항기상관측(AMOS) | 항공기의 안전한 운항을 지원하기 위해 전국의 7개소 공항에서 공항기상관측을 실시합니다. / 공항기상관측장비(Aerodrome Meteorological Observation System)는 항공기... | - | 2005년 2월 ∼ 현재(지점별 상이함) / 분, 시간, 일 자료 | typ01 | 0 |
| 14 | 항공기상 | 260 | 공항예·특보 | - | - | - / - | typ02/openApi | 11 |
| 14 | 항공기상 | 262 | AMDAR 관측 | - | - | - / - | typ01 | 0 |
| 14 | 항공기상 | 933 | 공항기상정보 | - | - | - / - | typ02/openApi | 1 |
| 14 | 항공기상 | 1043 | 저고도 기상지원 | - 저고도 중요기상예보(SIGWX): 인천비행정보구역에서 항공기 운항에 영향을 줄 수 있는 기상현상에 대해 발표하는 항공기상예보 / - 저고도 한반도 WINTEM(바람기온): 300∼3,000m ... | - 저고도 중요기상예보(SIGWX): 요소 종류, 요소 이름, 위칫값 등 / - 저고도 한반도 WINTEM(바람기온): 위도, 경도, 풍향, 풍속, 바람 등 / - 저고도 난류예측자료: 고도, 난... | - 저고도 중요기상예보(SIGWX): 2024. 02. 05. 11UTC ~ / - 저고도 한반도 WINTEM(바람기온): ... / - 저고도 중요기상예보(SIGWX): 6시간(5, 11, 17, 23UTC) / - 저고도 한반도 WINTEM(바람기온): ... | typ01 | 0 |
| 14 | 항공기상 | 10655 | LIDAR 관측자료 | 기상관측장비인 라이다(LiDAR)로 관측한 자료를 격자별로 제공 | 수평바람장(HWIND) | - / 5분 | typ01 | 0 |
| 12 | 세계기상 | 298 | GTS 관측 | 기상전문이란 기상관측에 의해 생산 · 수집된 자료를 교환하기 위해 송신에 적합하게 WMO에 의해서 명시된 국제적 규정에 따라 만든 자료를 말합니다. / 세계기상통신망인 GTS(Global Tele... | - | 1996년 1월 ∼ 현재(요소별 상이함) / 일, 시간 자료(요소별 상이함) | typ01, typ02/openApi | 3 |
| 12 | 세계기상 | 322 | GTS 지점정보 | - | - | - / - | typ01, typ02/openApi | 1 |
| 12 | 세계기상 | 988 | NCEI 관측·통계 | NCEI에서 수집한 전세계 기상관측 및 통계자료를 제공합니다. / ※ NCEI(National Centers for Environmental Information, 국립환경정보센터)는 미국 NOA... | (지상) 시간자료,일자료,월자료,연자료 / (고층) 시간자료 / (해양) 시간자료 | (지상) 시간자료: 1901년 ~/ 일자료: 1929년~/ 월자료: 1763년~/ 연자료: 1763년~ / (고층) 일자료:... / - | typ01 | 0 |

## Structured Operation Status

The source of truth for callable status is `src/ummaya/tools/kma/apihub_catalog.py`. The 2026-05-26 sweep adds the 60 operations that were present in official APIHub pages but absent from the previous 85-operation structured catalog; those new operations remain inactive unless utilization approval and direct curl response proof are captured.

| Category | Operation | Approval | Availability |
|---|---|---|---|
| 2 지상관측 | `AwsMtlyInfoService/getAwsStnLstTbl` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsMtlyInfoService/getDailyAwsData` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsMtlyInfoService/getMmSumry` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsMtlyInfoService/getNote` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsYearlyInfoService/getAwsStnLstTbl` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsYearlyInfoService/getNote` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsYearlyInfoService/getStnbyMmSumry` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `AwsYearlyInfoService/getYearSumry` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `SfcMtlyInfoService/getDailyWthrData` | `approved` | `active` |
| 2 지상관측 | `SfcMtlyInfoService/getMmSumry` | `approved` | `active` |
| 2 지상관측 | `SfcMtlyInfoService/getMmSumry2` | `approved` | `active` |
| 2 지상관측 | `SfcMtlyInfoService/getNote` | `approved` | `active` |
| 2 지상관측 | `SfcMtlyInfoService/getSfcStnLstTbl` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getAvgTaAnamaly` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getRnAnamaly` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getStnPhnmnData` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getStnPhnmnData2` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getStnPhnmnData3` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getYearSumry` | `approved` | `active` |
| 2 지상관측 | `SfcYearlyInfoService/getYearSumry2` | `approved` | `active` |
| 2 지상관측 | `YdstInfoService/getYdstObs` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `YdstInfoService/getYdstSatlitImg` | `approval_pending` | `approval_pending` |
| 2 지상관측 | `YdstInfoService/getYdstSfcChart` | `approval_pending` | `approval_pending` |
| 3 해양관측 | `SeaMtlyInfoService/getBuoyLstTbl` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getBuoyMmSumry` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getBuoyMmSumry2` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getDailyBuoy` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getDailyLhaws` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getDailyWaveBuoy` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getLhawsLstTbl` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getLhawsMmSumry` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getLhawsMmSumry2` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getNote` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getObsOpenYear` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getWaveBuoyLstTbl` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getWaveBuoyMmSumry` | `approved` | `active` |
| 3 해양관측 | `SeaMtlyInfoService/getWaveBuoyMmSumry2` | `approved` | `active` |
| 4 고층관측 | `UppMtlyInfoService/getMaxWind` | `approved` | `active` |
| 4 고층관측 | `UppMtlyInfoService/getNote` | `approved` | `active` |
| 4 고층관측 | `UppMtlyInfoService/getStdIsbrsfValue` | `approved` | `active` |
| 4 고층관측 | `UppMtlyInfoService/getTaHmLevel` | `approved` | `active` |
| 4 고층관측 | `UppMtlyInfoService/getUppLstTbl` | `approved` | `active` |
| 4 고층관측 | `UppMtlyInfoService/getWindLevel` | `approved` | `active` |
| 5 레이더 | `WethrBasicInfoService/getRadarObsStn` | `approval_pending` | `approval_pending` |
| 5 레이더 | `WthrRadarInfoService/getCompCappiQcdAll` | `approved` | `active` |
| 5 레이더 | `WthrRadarInfoService/getCompCappiQcdArea` | `approved` | `active` |
| 5 레이더 | `WthrRadarInfoService/getSiteCappiQcdAll` | `approval_pending` | `approval_pending` |
| 5 레이더 | `WthrRadarInfoService/getSiteCappiQcdArea` | `approval_pending` | `approval_pending` |
| 6 위성 | `CloudSatlitInfoService/getGk2aappsAll` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2aappsArea` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2aclaAll` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2aclaArea` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2acldAll` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2acldArea` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2adcoewAll` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2adcoewArea` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2afogAll` | `approved` | `active` |
| 6 위성 | `CloudSatlitInfoService/getGk2afogArea` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aIrAll` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aIrArea` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aNrAll` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aNrArea` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aSwAll` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aSwArea` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aViAll` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aViArea` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aWvAll` | `approved` | `active` |
| 6 위성 | `WthrSatlitInfoService/getGk2aWvArea` | `approved` | `active` |
| 7 지진/화산 | `EqkInfoService/getEqkMsg` | `approved` | `active` |
| 7 지진/화산 | `EqkInfoService/getEqkMsgList` | `approved` | `active` |
| 7 지진/화산 | `EqkInfoService/getTsunamiMsg` | `approval_pending` | `approval_pending` |
| 7 지진/화산 | `EqkInfoService/getTsunamiMsgList` | `approval_pending` | `approval_pending` |
| 8 태풍 | `SfcYearlyInfoService/getTyphoonList` | `approved` | `active` |
| 9 수치모델 | `KIMModelInfoService/getKIMLdapsUnisAll` | `approved` | `active` |
| 9 수치모델 | `KIMModelInfoService/getKIMLdapsUnisArea` | `approved` | `active` |
| 9 수치모델 | `KIMModelInfoService/getKIMRdapsUnisAll` | `approved` | `active` |
| 9 수치모델 | `KIMModelInfoService/getKIMRdapsUnisArea` | `approved` | `active` |
| 9 수치모델 | `NwpModelInfoService/getLdapsUnisAll` | `approved` | `retired` |
| 9 수치모델 | `NwpModelInfoService/getLdapsUnisArea` | `approved` | `retired` |
| 9 수치모델 | `NwpModelInfoService/getRdapsUnisAll` | `approved` | `retired` |
| 9 수치모델 | `NwpModelInfoService/getRdapsUnisArea` | `approved` | `retired` |
| 9 수치모델 | `WthrChartInfoService/getAuxillaryChart` | `approved` | `upstream_unavailable` |
| 9 수치모델 | `WthrChartInfoService/getSurfaceChart` | `approved` | `upstream_unavailable` |
| 10 예특보 | `FcstZoneInfoService/getFcstZoneCd` | `approval_pending` | `approval_pending` |
| 10 예특보 | `MidFcstInfoService/getMidFcst` | `approval_pending` | `approval_pending` |
| 10 예특보 | `MidFcstInfoService/getMidLandFcst` | `approval_pending` | `approval_pending` |
| 10 예특보 | `MidFcstInfoService/getMidSeaFcst` | `approval_pending` | `approval_pending` |
| 10 예특보 | `MidFcstInfoService/getMidTa` | `approval_pending` | `approval_pending` |
| 10 예특보 | `VilageFcstInfoService_2.0/getFcstVersion` | `approved` | `active` |
| 10 예특보 | `VilageFcstInfoService_2.0/getUltraSrtFcst` | `approved` | `active` |
| 10 예특보 | `VilageFcstInfoService_2.0/getUltraSrtNcst` | `approved` | `active` |
| 10 예특보 | `VilageFcstInfoService_2.0/getVilageFcst` | `approved` | `active` |
| 10 예특보 | `VilageFcstMsgService/getLandFcst` | `approved` | `active` |
| 10 예특보 | `VilageFcstMsgService/getSeaFcst` | `approved` | `active` |
| 10 예특보 | `VilageFcstMsgService/getWthrSituation` | `approved` | `active` |
| 10 예특보 | `WethrBasicInfoService/getWrnZoneCd` | `approval_pending` | `approval_pending` |
| 12 세계기상 | `GtsInfoService/getBuoy` | `approved` | `upstream_unavailable` |
| 12 세계기상 | `GtsInfoService/getGtsStn` | `approval_pending` | `approval_pending` |
| 12 세계기상 | `GtsInfoService/getSynop` | `approved` | `upstream_unavailable` |
| 12 세계기상 | `GtsInfoService/getTemp` | `approved` | `upstream_unavailable` |
| 14 항공기상 | `AftnAmmService/getMetar` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AftnAmmService/getSigmet` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AftnAmmService/getTaf` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AirInfoService/getAirInfo` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AirPortService/getAirPort` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmIwxxmService/getAirmet` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmIwxxmService/getMetar` | `approved` | `upstream_unavailable` |
| 14 항공기상 | `AmmIwxxmService/getSigmet` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmIwxxmService/getTaf` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmService/getAirmet` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmService/getSigmet` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmService/getTaf` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `AmmService/getWarning` | `approval_pending` | `approval_pending` |
| 14 항공기상 | `SfcMtlyInfoService/getAirNote` | `approved` | `active` |
| 14 항공기상 | `SfcMtlyInfoService/getDailyAirData` | `approved` | `active` |
| 14 항공기상 | `SfcMtlyInfoService/getrAirStnLstTbl` | `approved` | `active` |
| 14 항공기상 | `SfcYearlyInfoService/getAirStnInfo` | `approved` | `active` |
| 14 항공기상 | `SfcYearlyInfoService/getAirStnInfo2` | `approved` | `active` |
| 14 항공기상 | `SfcYearlyInfoService/getAirStnInfo3` | `approved` | `active` |
| 14 항공기상 | `SfcYearlyInfoService/getNote` | `approved` | `active` |
| 14 항공기상 | `SfcYearlyInfoService/getSfcStnLstTbl` | `approved` | `active` |
| 14 항공기상 | `SfcYearlyInfoService/getrAirStnLstTbl` | `approved` | `active` |
| 971 융합기상 | `BeachInfoservice/getSunInfoBeach` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `BeachInfoservice/getTideInfoBeach` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `BeachInfoservice/getTwBuoyBeach` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `BeachInfoservice/getUltraSrtFcstBeach` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `BeachInfoservice/getVilageFcstBeach` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `BeachInfoservice/getWhBuoyBeach` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FmlandWthrInfoService/getDayStatistics` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FmlandWthrInfoService/getFmlandPwn` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FmlandWthrInfoService/getFmlandVilageFcst` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FmlandWthrInfoService/getFmlandVilageNcst` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FmlandWthrInfoService/getMmStatistics` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FmlandWthrInfoService/getPureStatistics` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `FrstFcstInfoService/getFrstOcurFcst` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `HealthWthrIdxServiceV2/getOakPollenRiskIdxV2` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `HealthWthrIdxServiceV2/getPinePollenRiskIdxV2` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `HealthWthrIdxServiceV2/getWeedsPollenRiskndxV2` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `LivingWthrIdxServiceV3/getAirDiffusionIdxV3` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `LivingWthrIdxServiceV3/getSenTaIdxV3` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `LivingWthrIdxServiceV3/getUVIdxV3` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `RoadWthrInfoService/getCctvStnRoadWthr` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `RoadWthrInfoService/getStdNodeLinkRoadWw` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `TourStnInfoService/getCityTourClmIdx` | `approval_pending` | `approval_pending` |
| 971 융합기상 | `TourStnInfoService/getTourStnVilageFcst` | `approval_pending` | `approval_pending` |

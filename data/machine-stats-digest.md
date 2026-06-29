# 금형 사출 — 사출기(설비) 단위 가동·품질 통계 digest

- 데이터 출처: MinIO `mold-data/Dump2CSV_new/` (33001 분석 시스템이 사용하는 전처리본)
- 집계 단위: 사출기(injection machine, CSV의 `machine` 열 = `controller` 폴더와 1:1)
- 본 digest 의 모든 수치는 원본 CSV 를 직접 스트리밍해 집계한 실측값이다. 본문은 이 값만 인용한다.
- cycle_type 은 CSV 에 없어 가이드북 분류 규칙으로 재현했다(아래). 33001 공식 집계와 미세 차이 가능.

분류 규칙(순서대로 첫 매치):

| 유형 | 판정 |
|---|---|
| NO_SIGNAL | T1~T8_Max 전부 결측(NaN) — 센서 미연결 |
| SENSOR_ERROR | 장착 T채널 T_Max=0 이 2개↑, 또는 장착 P채널 P_Max=0 이 1개↑, 또는 사이클타임=0 |
| WARMUP | 장착 T채널 T_Detect 최댓값=0 — 레진 미도달(예열) |
| IDLE | 사이클타임 > P75 + 3×IQR — 비정상적 장시간(휴지) |
| NORMAL | 위 어디에도 안 걸림 — 분석 대상 |

(장착여부·IQR 임계는 각 사출기×금형 폴더 모집단에서 계산. 미장착 채널=폴더 95%↑가 T<30℃/P<50bar.)

## 1. 전체 총괄

- 가동 사출기: 15 대 (toprun 9대, woosung 6대)
- 가동 금형(고유 PartNo): 122 종
- 총 수집 사이클: 3,320,582 회

전체 사이클 유형 분포:

| 유형 | 건수 | 비중 |
|---|---|---|
| NORMAL | 387,898 | 11.68% |
| NO_SIGNAL | 2,900,949 | 87.36% |
| SENSOR_ERROR | 17,326 | 0.52% |
| WARMUP | 3,378 | 0.1% |
| IDLE | 11,031 | 0.33% |

## 2. 사출기별 설비 현황 총괄

| 사출기 | controller | 제조계열 | 도입연도 | 가동금형수 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|---|---|
| toprun_A3 | P-M02-2022-A142 | toprun | 2022 | 25 | 599,700 | 70,289 | 11.72% |
| toprun_C11 | P-M02-2024-A174 | toprun | 2024 | 31 | 501,376 | 20,558 | 4.1% |
| toprun_C7 | P-M02-2024-A181 | toprun | 2024 | 28 | 453,821 | 2,200 | 0.48% |
| toprun_C5 | P-M02-2024-A180 | toprun | 2024 | 24 | 443,354 | 15,570 | 3.51% |
| toprun_A2 | P-M02-2024-A172 | toprun | 2024 | 19 | 425,301 | 573 | 0.13% |
| toprun_D8 | P-M02-2023-A164 | toprun | 2023 | 9 | 317,548 | 205,419 | 64.69% |
| toprun_A5 | P-M02-2024-A177 | toprun | 2024 | 14 | 195,044 | 14,601 | 7.49% |
| woosung_40 | P-M02-2024-A184 | woosung | 2024 | 13 | 130,827 | 11,421 | 8.73% |
| toprun_C650-4 | P-M02-2025-A213 | toprun | 2025 | 6 | 103,932 | 796 | 0.77% |
| toprun_C650-5 | P-M02-2025-A216 | toprun | 2025 | 7 | 69,061 | 796 | 1.15% |
| woosung_42 | P-M02-2024-A186 | woosung | 2024 | 12 | 46,119 | 25,585 | 55.48% |
| woosung_54 | P-M02-2025-A224 | woosung | 2025 | 4 | 25,674 | 12,663 | 49.32% |
| woosung_45 | P-M02-2025-A222 | woosung | 2025 | 2 | 4,915 | 4,030 | 81.99% |
| woosung_48 | P-M02-2025-A220 | woosung | 2025 | 3 | 3,709 | 3,285 | 88.57% |
| woosung_37 | P-M02-2024-A185 | woosung | 2024 | 3 | 201 | 112 | 55.72% |

## 3. 사출기별 사이클 유형 분해 (건수)

| 사출기 | NORMAL | NO_SIGNAL | SENSOR_ERROR | WARMUP | IDLE | 합계 |
|---|---|---|---|---|---|---|
| toprun_A3 | 70,289 | 528,567 | 36 | 267 | 541 | 599,700 |
| toprun_C11 | 20,558 | 480,351 | 22 | 154 | 291 | 501,376 |
| toprun_C7 | 2,200 | 451,264 | 18 | 41 | 298 | 453,821 |
| toprun_C5 | 15,570 | 427,103 | 258 | 116 | 307 | 443,354 |
| toprun_A2 | 573 | 424,674 | 4 | 9 | 41 | 425,301 |
| toprun_D8 | 205,419 | 102,023 | 6,139 | 576 | 3,391 | 317,548 |
| toprun_A5 | 14,601 | 179,270 | 18 | 956 | 199 | 195,044 |
| woosung_40 | 11,421 | 116,505 | 775 | 306 | 1,820 | 130,827 |
| toprun_C650-4 | 796 | 103,060 | 5 | 18 | 53 | 103,932 |
| toprun_C650-5 | 796 | 68,189 | 5 | 18 | 53 | 69,061 |
| woosung_42 | 25,585 | 15,851 | 995 | 702 | 2,986 | 46,119 |
| woosung_54 | 12,663 | 3,064 | 9,023 | 107 | 817 | 25,674 |
| woosung_45 | 4,030 | 834 | 3 | 10 | 38 | 4,915 |
| woosung_48 | 3,285 | 131 | 24 | 95 | 174 | 3,709 |
| woosung_37 | 112 | 63 | 1 | 3 | 22 | 201 |

### 3-1. 사출기별 사이클 유형 분해 (비율 %)

| 사출기 | NORMAL% | NO_SIGNAL% | SENSOR_ERROR% | WARMUP% | IDLE% |
|---|---|---|---|---|---|
| toprun_A3 | 11.72% | 88.14% | 0.01% | 0.04% | 0.09% |
| toprun_C11 | 4.1% | 95.81% | 0.0% | 0.03% | 0.06% |
| toprun_C7 | 0.48% | 99.44% | 0.0% | 0.01% | 0.07% |
| toprun_C5 | 3.51% | 96.33% | 0.06% | 0.03% | 0.07% |
| toprun_A2 | 0.13% | 99.85% | 0.0% | 0.0% | 0.01% |
| toprun_D8 | 64.69% | 32.13% | 1.93% | 0.18% | 1.07% |
| toprun_A5 | 7.49% | 91.91% | 0.01% | 0.49% | 0.1% |
| woosung_40 | 8.73% | 89.05% | 0.59% | 0.23% | 1.39% |
| toprun_C650-4 | 0.77% | 99.16% | 0.0% | 0.02% | 0.05% |
| toprun_C650-5 | 1.15% | 98.74% | 0.01% | 0.03% | 0.08% |
| woosung_42 | 55.48% | 34.37% | 2.16% | 1.52% | 6.47% |
| woosung_54 | 49.32% | 11.93% | 35.14% | 0.42% | 3.18% |
| woosung_45 | 81.99% | 16.97% | 0.06% | 0.2% | 0.77% |
| woosung_48 | 88.57% | 3.53% | 0.65% | 2.56% | 4.69% |
| woosung_37 | 55.72% | 31.34% | 0.5% | 1.49% | 10.95% |

## 4. 데이터 품질(센서 안정성) — 센서 에러 비율 랭킹

센서계 에러 = NO_SIGNAL + SENSOR_ERROR (수집 안정성 문제, 제품 불량 아님).

| 사출기 | NO_SIGNAL | SENSOR_ERROR | 센서에러합 | 센서에러율 |
|---|---|---|---|---|
| toprun_A2 | 424,674 | 4 | 424,678 | 99.85% |
| toprun_C7 | 451,264 | 18 | 451,282 | 99.44% |
| toprun_C650-4 | 103,060 | 5 | 103,065 | 99.17% |
| toprun_C650-5 | 68,189 | 5 | 68,194 | 98.74% |
| toprun_C5 | 427,103 | 258 | 427,361 | 96.39% |
| toprun_C11 | 480,351 | 22 | 480,373 | 95.81% |
| toprun_A5 | 179,270 | 18 | 179,288 | 91.92% |
| woosung_40 | 116,505 | 775 | 117,280 | 89.65% |
| toprun_A3 | 528,567 | 36 | 528,603 | 88.14% |
| woosung_54 | 3,064 | 9,023 | 12,087 | 47.08% |
| woosung_42 | 15,851 | 995 | 16,846 | 36.53% |
| toprun_D8 | 102,023 | 6,139 | 108,162 | 34.06% |
| woosung_37 | 63 | 1 | 64 | 31.84% |
| woosung_45 | 834 | 3 | 837 | 17.03% |
| woosung_48 | 131 | 24 | 155 | 4.18% |

## 5. 가동 안정성 — WARMUP / IDLE 비율

| 사출기 | WARMUP | WARMUP% | IDLE | IDLE% |
|---|---|---|---|---|
| woosung_37 | 3 | 1.49% | 22 | 10.95% |
| woosung_42 | 702 | 1.52% | 2,986 | 6.47% |
| woosung_48 | 95 | 2.56% | 174 | 4.69% |
| woosung_54 | 107 | 0.42% | 817 | 3.18% |
| woosung_40 | 306 | 0.23% | 1,820 | 1.39% |
| toprun_D8 | 576 | 0.18% | 3,391 | 1.07% |
| woosung_45 | 10 | 0.2% | 38 | 0.77% |
| toprun_A5 | 956 | 0.49% | 199 | 0.1% |
| toprun_A3 | 267 | 0.04% | 541 | 0.09% |
| toprun_C650-5 | 18 | 0.03% | 53 | 0.08% |
| toprun_C5 | 116 | 0.03% | 307 | 0.07% |
| toprun_C7 | 41 | 0.01% | 298 | 0.07% |
| toprun_C11 | 154 | 0.03% | 291 | 0.06% |
| toprun_C650-4 | 18 | 0.02% | 53 | 0.05% |
| toprun_A2 | 9 | 0.0% | 41 | 0.01% |

## 6. 사출기별 가동 금형 상세

### toprun_A3 (P-M02-2022-A142) — 금형 25종, 총 599,700 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MCK71605701 | [HONDA]TSU | COVER BOTTOM | 255,761 | 0 | 0.0% |
| MCK71758701 | [VW]FPK | COVER REAR | 129,477 | 55,232 | 42.66% |
| MCK71605601 | [HONDA]TSU | COVER TOP | 51,169 | 0 | 0.0% |
| MBN63343301 | [GM]K2XX | CASE FRONT | 19,794 | 0 | 0.0% |
| MBN65562801 | [VW]OCU4 | CASE BOTTOM | 16,479 | 0 | 0.0% |
| MBN64923101 | INFO3.5L | CASE FRONT | 12,877 | 0 | 0.0% |
| MGC66100101 | [RENAULT]ULC4.5_PY1B | PANEL FRONT | 10,907 | 0 | 0.0% |
| MCK71924401 | [MB]BR206M | COVER REAR | 10,029 | 6,844 | 68.24% |
| MBN65302502 | [RENAULT]RBC | CASE FRONT | 9,931 | 0 | 0.0% |
| IMBN66466901 | [BMW]CHUD | RAY TUBE DOWN | 9,308 | 0 | 0.0% |
| MGC66425401 | [PORSCHE]992PA | PANEL FRONT RHD | 8,872 | 0 | 0.0% |
| MGC66451901 | [RENAULT]XJI | PANEL REAR | 8,449 | 8,213 | 97.21% |
| MCK 71390801 | [RENAULT]ULC4.5_X52 | COVER REAR | 8,222 | 0 | 0.0% |
| MGC 66391701 | [PORSCHE]E3PA_CID | PANEL FRONT | 8,216 | 0 | 0.0% |
| MGC66391401 | [PORSCHE]G3_CID | PANEL FRONT G3 CID | 8,043 | 0 | 0.0% |
| MAZ64563301 | [GM]GAMMA | MONITOR BRACKET | 5,717 | 0 | 0.0% |
| MGC66391801 | [PORSCHE]E3PA_DID | PANEL FRONT DID LHD | 5,046 | 0 | 0.0% |
| MAZ67612701 | [PORSCHE]992PA | BRACKET BOTTOM | 4,154 | 0 | 0.0% |
| IMGC66361501 | [RENAULT]ULC4.5_HJD | PANER FRONT | 4,111 | 0 | 0.0% |
| MEG66460101 | [VW]ARHUD-RHD | HOLDER LCD BOTTOM RHD | 4,051 | 0 | 0.0% |
| MDQ66692301 | [BMW]AZV | PANEL GUIDE  FRONT DFE RHD | 3,283 | 0 | 0.0% |
| 4977-0187A | [LGD]LUCID34 | GUIDE HOLDER | 1,800 | 0 | 0.0% |
| MCR67507901 | [MB]MRA2-ICD | DECO REAR | 1,378 | 0 | 0.0% |
| IMBN65285701 | [GM]RSI | CASE FRONT | 1,356 | 0 | 0.0% |
| IMBN665225001 | [HONDA]19BMC | Case Front LHD | 1,270 | 0 | 0.0% |

### toprun_C11 (P-M02-2024-A174) — 금형 31종, 총 501,376 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| ABQ77542801 | [RENAUL]NISSAN-WCBS | TOP CASE | 197,579 | 0 | 0.0% |
| IMBN66466901 | [BMW]CHUD | RAYTUBE DOWN | 131,952 | 0 | 0.0% |
| MBN65604901 | [VW]OCU3-MQB37W | CASE BOTTOM 37W | 28,117 | 0 | 0.0% |
| MBN65302502 | [RENAULT]RBC | CASE FRONT | 27,104 | 0 | 0.0% |
| IMBNG63343301 | [GM]K2XX | case front | 26,317 | 0 | 0.0% |
| MGC66451901 | [RENAULT]XJI | PANEL REAR | 20,829 | 17,975 | 86.3% |
| MEG65879401 | [VW]AR-HUD-LHD | HOLDER LCD BOTTOM LHD | 20,201 | 0 | 0.0% |
| MCK71605601 | [HONDA]TSU | COVER TOP | 10,284 | 0 | 0.0% |
| MGC66425401 | [PORSCHE]992PA | 992PA RHD PANEL FRONT | 7,030 | 0 | 0.0% |
| IMGC66183001 | [BENTLEY]BENTLEY-AIT | PANEL FRONT AIT | 5,011 | 0 | 0.0% |
| MGC66391701 | [PORSCHE]E3PA-CID | PANEL FRONT E3PA CID | 4,908 | 0 | 0.0% |
| MGC66100101 | [RENAULT]PY1B | PAEL FRONT | 3,886 | 0 | 0.0% |
| IMDQ65436301 | [PORSCHE]MACAN-LZV | FRAME FRONT | 3,869 | 0 | 0.0% |
| MCK71924401 | [MERCEDES]BR206M | COVER REAR | 2,688 | 1,376 | 51.19% |
| MDQ66754701 | [BMW]AZV | PANEL GUIDE FRONT CID 4M RHD | 2,005 | 0 | 0.0% |
| 6944L-0023A | GMBUICK | DECO TRIM | 1,816 | 0 | 0.0% |
| IMGC65639401 | [BMW]RR2X | PANEL FRONT | 1,785 | 0 | 0.0% |
| MGC66160901 | [RENAULT]HBC | PANEL  FRONT | 1,569 | 0 | 0.0% |
| MBN66596001 | [JLR]RCCD | CASE BOTTOM | 1,480 | 491 | 33.18% |
| MDQ66692301 | [BMW]AZV | PANEL GUIDE FRONT DFE RHD | 1,123 | 0 | 0.0% |
| H24VVA0033A | [JLR]EMA-RCCD | CASE TOP | 815 | 716 | 87.85% |
| MBN63803301 | [JLR]EVAC_VCM | CASE BOTTOM | 618 | 0 | 0.0% |
| IMGC66385001 | [PORSCHE]E3PA-CLUSTER | PANEL REAR | 329 | 0 | 0.0% |
| MBN64610201 | [JLR]TCU3 | CASE TOP | 39 | 0 | 0.0% |
| MBN65583401 | [VW]OCU3-MQB37W | CASE TOP-37W | 5 | 0 | 0.0% |
| MDQ66754601 | [BMW]AZV | PANEL GUIDE FRONT CID 4M LHD | 4 | 0 | 0.0% |
| IMGC66361501 | [RENAULT]ULC4.5-HJD | PANEL FRONT | 3 | 0 | 0.0% |
| MCK71427001 | [RENAULT]ULC4.5-HJD | COVER REAR | 3 | 0 | 0.0% |
| MCK71605701 | [HONDA]TSU | COVER BOTTOM | 3 | 0 | 0.0% |
| ABQ76602101 | [JLR]TCU4 | TOP CASE | 2 | 0 | 0.0% |
| ACQ30306401 | [SYMC]Y450 | COVER REAR | 2 | 0 | 0.0% |

### toprun_C7 (P-M02-2024-A181) — 금형 28종, 총 453,821 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| IMGC66385001 | [PORSCHE]E3PA_CLUSTER | PANEL REAR | 112,612 | 0 | 0.0% |
| IMBN66466802 | [BMW]CHUD | RAYTUBE UP 4M | 102,327 | 0 | 0.0% |
| MCK71387901 | [SYMC]Y450 | PANEL FRONT | 49,279 | 0 | 0.0% |
| MBN65583401 | [VW]OCU3_MQB37W | CASE TOP | 37,575 | 0 | 0.0% |
| MBN65503301 | [JLR]TCU4 | TOP CASE | 27,044 | 0 | 0.0% |
| MNB66466501 | [BMW]CHUD | CASE TOP MAIN | 16,569 | 0 | 0.0% |
| MBN65604901 | [VW]OCU3_MQB37W | CASE BOTTOM 37W | 16,498 | 0 | 0.0% |
| MGC66414801 | [RENARULT]CCS3 | PANEL FRONT AIO | 16,316 | 0 | 0.0% |
| MEG65879401 | [VW]ARHUD | HOLDER LCD TOP  LHD | 12,465 | 0 | 0.0% |
| MGC66467301 | X1312 | Panel Front | 12,038 | 1,758 | 14.6% |
| MBN63343301 | [GM]K2XX | CASE FRONT | 11,990 | 0 | 0.0% |
| IMBN65385201 | [SYMC]C300_CLUSTER | CASE FRONT | 9,201 | 0 | 0.0% |
| MBN6483201 | [GM]GEN11 | CASE MAIN | 5,958 | 0 | 0.0% |
| MCK71129501 | [RENAULT]UCL4.5_PY1B | COVER REAR | 5,591 | 0 | 0.0% |
| MCK71427001 | [RENAULT]HJD | COVER REAR | 5,350 | 0 | 0.0% |
| MDQ68476901 | [PORSCHE]J1DUAL_PPR | FRONT FRAME PID | 4,958 | 0 | 0.0% |
| MCK71605601 | [HONDA]TSU | COVER TOP | 3,072 | 0 | 0.0% |
| 6944L-0023A | GMBUICK | DECO TRIM | 2,304 | 0 | 0.0% |
| IMCK71158301 | [BMW]GO1_LCI | COVER REAR GO1 LCI LHD | 955 | 0 | 0.0% |
| IMBN66466901 | [BMW]CHUD | RAY TUBE DOW | 503 | 0 | 0.0% |
| MGC66480801 | RENAULT_CCS_X1324 | PANEL REAR | 485 | 0 | 0.0% |
| MCK71924401 | [MB]BR206M | COVER REAR | 190 | 186 | 97.89% |
| MGC66451901 | [RENAULT]XJI | PANEL REAR | 176 | 158 | 89.77% |
| MGC66480701 | [RENAULT]X1324 | PANEL FRONT | 173 | 0 | 0.0% |
| MGC66467201 | [RENAULT]X1312 | PANER REAR | 116 | 37 | 31.9% |
| MGC30036501 | BBB_LATAM | Panel Front | 69 | 61 | 88.41% |
| IMB66466801 | [BMW]CHUD | RAYTUBE UP 4M | 4 | 0 | 0.0% |
| MGC66160901 | [RENAULT]HBC | PANEL FRONT | 3 | 0 | 0.0% |

### toprun_C5 (P-M02-2024-A180) — 금형 24종, 총 443,354 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| IMBN66466802 | [BMW]CHUD | RAYTUBE UP 4M | 113,428 | 0 | 0.0% |
| MBN64683201 | [GM]GEN11 | CASE MAIN | 82,270 | 0 | 0.0% |
| MBN66466501 | [BMW]CHUD | CASE TOP MAIN | 65,853 | 0 | 0.0% |
| MCK71565201 | [MB]BR214 | REAR FRAME 2D | 32,504 | 0 | 0.0% |
| MBN65503301 | [JLR]TCU4 | TOP CASE | 27,704 | 0 | 0.0% |
| MGC66467301 | X1312 | Panel Front | 23,194 | 11,321 | 48.81% |
| MBN66102701 | [NISSAN]WCBS | CASE TOP | 20,902 | 0 | 0.0% |
| MBN6334301 | [GM]K2XX | CASE FRONT | 14,323 | 0 | 0.0% |
| MCK67498901 | [GM]GEN10 | COVER TOP WITHOUT FEET | 13,888 | 0 | 0.0% |
| IMGC66160701 | [RENAULT]ULC4.5_X52 | PANEL FRONT | 12,835 | 0 | 0.0% |
| IMBN66466901 | [BMW]CHUD | RAY TUBE DOWN | 7,430 | 0 | 0.0% |
| MGC30036501 | BBB_LATAM | Panel Front | 6,716 | 698 | 10.39% |
| MGC66480701 | [RENAULT]X1324 | PANEL FRONT | 4,357 | 2,035 | 46.71% |
| IMGC66361501 | [RENAULT]ULC4.5_HJD | PANEL FRONT | 3,234 | 0 | 0.0% |
| MCK71605701 | [HONDA]TSU | COVER BOTTOM | 2,880 | 0 | 0.0% |
| MGE65818802 | [VW]ARHUD_LHD | HOLDER LCD TOP LHD | 2,205 | 0 | 0.0% |
| MGC66467201 | [RENAULT]X1312 | PANER REAR | 2,182 | 1,177 | 53.94% |
| MCK71427001 | [REANULT]ULC4.5_HJD | COVER REAR | 1,868 | 0 | 0.0% |
| MEG65879401 | [VW]ARHUD_LHD | HOLDER LCD BOTTOM LHD | 1,607 | 0 | 0.0% |
| MBN65302502 | [RENAULT]RBC | CASE FRONT | 1,605 | 0 | 0.0% |
| MCK70170801 | [SYMC]C300_CLUSTER | COVER REAR | 1,099 | 0 | 0.0% |
| IMGC66480701 | RENAULTCCS3X1324 | PANEL FRONT | 899 | 0 | 0.0% |
| MCK71924401 | [MB]BR206M | COVER REAR | 190 | 186 | 97.89% |
| MGC66451901 | [RENAULT]XJI | PANEL REAR | 181 | 153 | 84.53% |

### toprun_A2 (P-M02-2024-A172) — 금형 19종, 총 425,301 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MBN65302501 | [RENAUT]RBC | CASE FRONT | 104,637 | 0 | 0.0% |
| MBN63343301 | [GM]K2XX | CASE FRONT | 73,683 | 0 | 0.0% |
| MBN66466901 | [BMW]CHUD | RAYTUBE DOWN | 66,793 | 0 | 0.0% |
| MCK71565201 | [MB]BR214 | REAR FRAME 2D | 31,741 | 0 | 0.0% |
| MGC66414801 | [RENAULT]CCS3 | PANEL FRONT | 30,727 | 0 | 0.0% |
| MBN66466201 | [BMW]CHUD | CASE BOTTOM | 30,711 | 0 | 0.0% |
| MGC66391701 | [PORSCHE]E3PA_CID | PANEL FRONT | 25,542 | 0 | 0.0% |
| MCK71605601 | [HONDA]TSU | COVER TOP | 20,422 | 0 | 0.0% |
| MGC66425301 | [PORSCHE]992PA | PANEL FRONT LHD | 10,961 | 0 | 0.0% |
| 4977L-0187A | [LGD]LUCID34 | GUIDE HOLDER | 10,310 | 0 | 0.0% |
| MEG65879401 | [VW]ARHUD_LHD | HOLDER LCD BOTTOM LHD | 5,115 | 0 | 0.0% |
| MBN66587901 | [JLR]VCM | CASE BOTTOM | 4,842 | 0 | 0.0% |
| MCK71165201 | [MB]MRA2_ICD | COVER REAR H | 3,704 | 0 | 0.0% |
| MCK71390801 | [RENAULT]ULC4.5_X52 | COVER REAR | 2,939 | 0 | 0.0% |
| MGC66100101 | [RENAULT]ULC4.5_PY1B | PANEL FRONT | 2,547 | 0 | 0.0% |
| MGC66467301 | [RENAULT]X1312 | PANEL FRONT | 213 | 190 | 89.2% |
| MCK71924401 | [MB]BR206M | COVER REAR | 190 | 186 | 97.89% |
| MGC66451901 | [RENAULT]XJI | PANEL REAR | 176 | 158 | 89.77% |
| MGC66467201 | [RENAULT]X1312 | PANER REAR | 48 | 39 | 81.25% |

### toprun_D8 (P-M02-2023-A164) — 금형 9종, 총 317,548 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MCK71758701 | [VW]FPK | COVER REAR | 218,665 | 204,425 | 93.49% |
| MCK67461001 | [SYMC]Y450 | COVER LENS | 50,420 | 0 | 0.0% |
| MKC66600401 | [SYMC]C300_CLUSTER | WINDOW FRONT | 23,146 | 0 | 0.0% |
| IMGC66385001 | [PORSCHE]E3PA | PANEL REAR | 17,604 | 0 | 0.0% |
| MEG65818802 | VW-AR-HUD-LHD | Holder LCD Top Lhd | 4,540 | 0 | 0.0% |
| MGC66478801 | RENAULTX1320 | Panel Rear | 1,402 | 0 | 0.0% |
| MGC30036601 | BBB_LATAM | Panel Rear | 816 | 722 | 88.48% |
| 6944L_0023A | [GM]BUICK | DECO_TRIM | 641 | 0 | 0.0% |
| MGC30036501 | BBB_LATAM | Panel Front | 314 | 272 | 86.62% |

### toprun_A5 (P-M02-2024-A177) — 금형 14종, 총 195,044 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MGC66414801 | [RENAULT]CCS3 | PANEL FRONT AIO | 54,421 | 0 | 0.0% |
| IMBN63343301 | [GM]K2XX | CASE FRONT | 39,664 | 0 | 0.0% |
| MCK69168901 | [JLR]TCU3 | COVER BUB | 27,762 | 0 | 0.0% |
| MCK 71605801 | [HONDA]TSU | COVER BUB | 26,185 | 0 | 0.0% |
| MCR67228501 | [GM]SI | DECO FRONT | 17,101 | 0 | 0.0% |
| MGC66451901 | [RENAULT]XJI | PANEL REAR | 14,093 | 13,147 | 93.29% |
| MBN66102701 | [NISSAN]WCBS | CASE TOP | 8,707 | 1,225 | 14.07% |
| MGC66100101 | [RENAULT]ULC4.5_PY1B | PANEL FRONT | 6,088 | 0 | 0.0% |
| MCK71924401 | BR206M | COVER REAR | 751 | 0 | 0.0% |
| MGC66467301 | [RENAULT]X1312 | PANEL FRONT | 213 | 190 | 89.2% |
| MGC66467201 | [RENAULT]X1312 | PANER REAR | 48 | 39 | 81.25% |
| MBN66596001 | [JLR]RCCD | CASE BOTTOM | 7 | 0 | 0.0% |
| MAZ67113101+MAZ67113201 | [MB]EVA2_E2H_RHD | TRIM BRACKET DRIVER RHD | 2 | 0 | 0.0% |
| MBN66595901 | [JLR]RCCD | CASE TOP | 2 | 0 | 0.0% |

### woosung_40 (P-M02-2024-A184) — 금형 13종, 총 130,827 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MBN66622301 | ICON25SF | CASE TOP | 91,899 | 647 | 0.7% |
| MGC66367901 | SP3_LHD | Panel Front | 20,434 | 116 | 0.57% |
| EAV28001010 | V28A | CASE TOP | 5,423 | 4,888 | 90.13% |
| MCK71925501 | [HKMC]QV | COVER REAR(LHD) | 3,591 | 1,605 | 44.7% |
| MCK71904101 | [JLR]EMAFDD | COVER FRONT | 3,360 | 1,174 | 34.94% |
| MCK71869301 | BR223_3D | Rear Cover | 2,222 | 1,711 | 77.0% |
| MCK71922201 | [HKMC]SP3 | COVER REAR (LHD) | 1,512 | 203 | 13.43% |
| MCK71986401 | AUDI-FF | COVER REAR | 1,116 | 177 | 15.86% |
| ACQ30767301 | [MB]BR223MOPF2D | COVER REAR | 916 | 747 | 81.55% |
| TEST | HKMC-QV(RHD) | Cover Rear | 221 | 153 | 69.23% |
| MCK17925601 | [HKMC]QV | COVER REAR (RHD) | 119 | 0 | 0.0% |
| m0000000000 | TEST | dumy | 13 | 0 | 0.0% |
| MGJ66282101 | ARHUD | MIRROR SUPORT | 1 | 0 | 0.0% |

### toprun_C650-4 (P-M02-2025-A213) — 금형 6종, 총 103,932 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MBN64683201 | [GM]GEN11 | Case Main | 95,029 | 0 | 0.0% |
| MBN66102701 | [NISSAN]WCBS | CASE TOP | 8,002 | 0 | 0.0% |
| MCK30007201 | [HYUNDAI]OVK_R | COVER REAR | 340 | 324 | 95.29% |
| MGC30028001 | [HYUNDAI]OVK_R | PANEL FRONT | 281 | 232 | 82.56% |
| MCK71950601 | [HYUNDAI]TK_R | COVER REAR RHD | 278 | 240 | 86.33% |
| MCK71929101 | [HYUNDAI]TK_L | COVER REAR LHD | 2 | 0 | 0.0% |

### toprun_C650-5 (P-M02-2025-A216) — 금형 7종, 총 69,061 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| ABQ76540401 | [GM]GEN11 | CASE MAIN | 55,451 | 0 | 0.0% |
| MGC66469001 | [HYUNDAI]TK | PANEL FRONT | 8,503 | 0 | 0.0% |
| MCK71929101 | [HYUNDAI]TK_L | COVER REAR LHD | 3,099 | 0 | 0.0% |
| MBN66102701 | [NISSAN]WCBS | CASE TOP | 1,134 | 0 | 0.0% |
| MCK30007201 | [HYUNDAI]OVK_R | COVER REAR | 340 | 324 | 95.29% |
| MCK71950601 | [HYUNDAI]TK_R | COVER REAR RHD | 280 | 240 | 85.71% |
| MGC30028001 | [HYUNDAI]OVK_R | PANEL FRONT | 254 | 232 | 91.34% |

### woosung_42 (P-M02-2024-A186) — 금형 12종, 총 46,119 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| TEST | CR2_copied | COVER REAR | 16,509 | 5,424 | 32.85% |
| MCK71986401 | CR2_AUDI | COVER REAR | 10,332 | 7,950 | 76.95% |
| MCK71925501 | QV_LHD | Cover Rear | 5,462 | 1,550 | 28.38% |
| MGC66367901 | SP3_LHD | Panel Front | 3,762 | 2,819 | 74.93% |
| MGC30048001 | NX5 | PANEL PRONT | 3,383 | 3,032 | 89.62% |
| MCK71922301 | [HKMC]SP3 | COVER REAR(RHD) | 2,562 | 2,372 | 92.58% |
| MCK71922201 | SP3_LHD | Cover Rear | 1,161 | 740 | 63.74% |
| MCK71839301 | BR223_2D | Cover Rear | 1,075 | 813 | 75.63% |
| MCK30113301 | CN8,NX5 | COVER REAR | 828 | 735 | 88.77% |
| ㅅ쇼 | ㄱㄹㄹ | ㅅㅅㅅ | 641 | 0 | 0.0% |
| MCK71925601 | QV_RHD | Cover Rear | 320 | 82 | 25.62% |
| MCK30110501 | QY2 | COVER REAR | 84 | 68 | 80.95% |

### woosung_54 (P-M02-2025-A224) — 금형 4종, 총 25,674 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MCK71961001 | 65UA75 | Cover Rear | 18,260 | 8,094 | 44.33% |
| MCK00000000 | 65INCH | Cover Rear | 6,658 | 3,932 | 59.06% |
| MGC30048001 | CN8 | PANEL PRONT | 554 | 448 | 80.87% |
| MCK30113301 | NX5,CN8 | COVER  RERA | 202 | 189 | 93.56% |

### woosung_45 (P-M02-2025-A222) — 금형 2종, 총 4,915 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MCK30110501 | QVLHDREAR | COVER REAR | 4,680 | 3,814 | 81.5% |
| MGC30048001 | NX5 | PANEL PRONT | 235 | 216 | 91.91% |

### woosung_48 (P-M02-2025-A220) — 금형 3종, 총 3,709 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MGC30048001 | NX5 | PANEL PRONT | 2,861 | 2,634 | 92.07% |
| MCK30113301 | NX5,CN8 | COVER  RERA | 773 | 595 | 76.97% |
| MCK30110501 | QY2 | COVER REAR | 75 | 56 | 74.67% |

### woosung_37 (P-M02-2024-A185) — 금형 3종, 총 201 사이클

| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |
|---|---|---|---|---|---|
| MCK71869301 | BR223_3D | Rear Cover | 138 | 112 | 81.16% |
| MBN665989 | BMW | BOTTOM | 58 | 0 | 0.0% |
| MBN664989 | BMW | case bottom | 5 | 0 | 0.0% |

## 7. 여러 사출기에 걸쳐 사용된 금형 (N:N)

고유 금형 122종 중 44종이 2대 이상의 사출기에서 가동되었다.

| 금형(PartNo) | 사용 사출기 수 | 사출기 목록 |
|---|---|---|
| MCK71924401 | 6 | toprun_A2, toprun_A3, toprun_A5, toprun_C11, toprun_C5, toprun_C7 |
| MGC66451901 | 6 | toprun_A2, toprun_A3, toprun_A5, toprun_C11, toprun_C5, toprun_C7 |
| IMBN66466901 | 4 | toprun_A3, toprun_C11, toprun_C5, toprun_C7 |
| MCK71605601 | 4 | toprun_A2, toprun_A3, toprun_C11, toprun_C7 |
| MGC66100101 | 4 | toprun_A2, toprun_A3, toprun_A5, toprun_C11 |
| MEG65879401 | 4 | toprun_A2, toprun_C11, toprun_C5, toprun_C7 |
| MGC66467201 | 4 | toprun_A2, toprun_A5, toprun_C5, toprun_C7 |
| MGC66467301 | 4 | toprun_A2, toprun_A5, toprun_C5, toprun_C7 |
| MBN66102701 | 4 | toprun_A5, toprun_C5, toprun_C650-4, toprun_C650-5 |
| MGC30048001 | 4 | woosung_42, woosung_45, woosung_48, woosung_54 |
| IMGC66361501 | 3 | toprun_A3, toprun_C11, toprun_C5 |
| MBN63343301 | 3 | toprun_A2, toprun_A3, toprun_C7 |
| MBN65302502 | 3 | toprun_A3, toprun_C11, toprun_C5 |
| MCK71605701 | 3 | toprun_A3, toprun_C11, toprun_C5 |
| IMGC66385001 | 3 | toprun_C11, toprun_C7, toprun_D8 |
| MGC30036501 | 3 | toprun_C5, toprun_C7, toprun_D8 |
| MGC66414801 | 3 | toprun_A2, toprun_A5, toprun_C7 |
| MCK71427001 | 3 | toprun_C11, toprun_C5, toprun_C7 |
| MCK30110501 | 3 | woosung_42, woosung_45, woosung_48 |
| MCK30113301 | 3 | woosung_42, woosung_48, woosung_54 |
| MCK71758701 | 2 | toprun_A3, toprun_D8 |
| MDQ66692301 | 2 | toprun_A3, toprun_C11 |
| MGC66425401 | 2 | toprun_A3, toprun_C11 |
| MCK71565201 | 2 | toprun_A2, toprun_C5 |
| MGC66391701 | 2 | toprun_A2, toprun_C11 |
| 6944L-0023A | 2 | toprun_C11, toprun_C7 |
| MBN65583401 | 2 | toprun_C11, toprun_C7 |
| MBN65604901 | 2 | toprun_C11, toprun_C7 |
| MBN66596001 | 2 | toprun_A5, toprun_C11 |
| MGC66160901 | 2 | toprun_C11, toprun_C7 |
| IMBN66466802 | 2 | toprun_C5, toprun_C7 |
| MBN64683201 | 2 | toprun_C5, toprun_C650-4 |
| MBN65503301 | 2 | toprun_C5, toprun_C7 |
| MGC66480701 | 2 | toprun_C5, toprun_C7 |
| MCK71869301 | 2 | woosung_37, woosung_40 |
| MCK71922201 | 2 | woosung_40, woosung_42 |
| MCK71925501 | 2 | woosung_40, woosung_42 |
| MCK71986401 | 2 | woosung_40, woosung_42 |
| MGC66367901 | 2 | woosung_40, woosung_42 |
| TEST | 2 | woosung_40, woosung_42 |
| MCK30007201 | 2 | toprun_C650-4, toprun_C650-5 |
| MCK71929101 | 2 | toprun_C650-4, toprun_C650-5 |
| MCK71950601 | 2 | toprun_C650-4, toprun_C650-5 |
| MGC30028001 | 2 | toprun_C650-4, toprun_C650-5 |

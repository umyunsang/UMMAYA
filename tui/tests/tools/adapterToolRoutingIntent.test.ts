import { afterEach, describe, expect, test } from 'bun:test'
import {
  clearManifestCache,
  ingestManifestFrame,
} from '../../src/services/api/adapterManifest.js'
import {
  selectTopKAdapterToolNamesForQuery,
} from '../../src/tools/AdapterTool/AdapterTool.js'

function entry(toolId: string, searchHint: string) {
  return {
    tool_id: toolId,
    name: toolId,
    primitive: 'find' as const,
    policy_authority_url: 'https://www.data.go.kr/',
    source_mode: 'live' as const,
    search_hint: searchHint,
    llm_description: searchHint,
    input_schema_json: {
      type: 'object',
      properties: {},
      additionalProperties: false,
    },
  }
}

function ingestAdversarialPublicDataManifest(): void {
  clearManifestCache()
  ingestManifestFrame({
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'routing-intent-test',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9RT',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: [
      entry('kma_current_observation', '날씨 기상 현재 관측 대체 후보'),
      entry('airkorea_ctprvn_air_quality', 'AirKorea 에어코리아 대기질 미세먼지 서울 중구'),
      entry('mock_lookup_module_gov24_certificate', '정부24 증명서 민원 mock'),
      entry('mock_kftc_opengiro_payment_send_v1', '결제 납부 요금 지로 mock'),
      entry('moj_village_lawyer_lookup', '법무부 마을변호사 부산 사하구'),
      entry('ccourt_publication_documents', '헌법재판소 발간자료 기본권'),
      entry('koroad_accident_hazard_search', 'KOROAD 교통사고 위험 지점'),
      entry('tago_bus_route_search', 'TAGO 버스 노선 route 1001 부산'),
      entry('tago_bus_station_search', 'TAGO 버스 정류장 station'),
      entry('tago_bus_arrival_search', 'TAGO 버스 도착정보 arrival'),
      entry('gyeryong_assistive_device_charging_place_locate', '계룡시 장애인 보조기기 충전소'),
      entry('mois_emergency_call_box_lookup', '비상벨 비상호출함 긴급신고함'),
      entry('mfds_easy_drug_info_lookup', '식약처 의약품 쉬운 정보 타이레놀'),
      entry('mpm_public_job_lookup', '인사혁신처 공무원 채용 공고'),
      entry('mss_sme_support_notice_lookup', '중소벤처기업부 지원사업 공고'),
      entry('pps_shopping_mall_product_lookup', '조달청 나라장터 쇼핑몰 노트북 제품'),
      entry('mof_ocean_water_quality_check', '해양수질 자동 측정'),
      entry('kcue_finance_regional_tuition', '대학알리미 지역별 등록금'),
      entry('fsc_corporate_finance_summary', '금융위원회 기업금융 요약'),
      entry('ftc_large_group_status', '공정거래위원회 대기업집단 현황'),
    ],
    manifest_hash: 'f'.repeat(64),
    emitter_pid: 12345,
  })
}

afterEach(() => {
  clearManifestCache()
})

describe('adapter tool routing intent', () => {
  test('keeps legal public-data requests off stale weather surface', () => {
    ingestAdversarialPublicDataManifest()

    const names = selectTopKAdapterToolNamesForQuery(
      '부산 사하구 마을변호사 정보를 법무부 공식 도구로 찾고 헌법재판소 발간자료에서 기본권 자료도 찾아줘. 날씨로 대체하지 말고 법무부와 헌재 도구만 써.',
      5,
    )

    expect(names).toContain('moj_village_lawyer_lookup')
    expect(names).toContain('ccourt_publication_documents')
    expect(names).not.toContain('kma_current_observation')
  })

  test('keeps legal public-data requests off weather surface when later verb says 확인', () => {
    ingestAdversarialPublicDataManifest()

    const names = selectTopKAdapterToolNamesForQuery(
      '날씨로 대체하지 마. 부산 사하구 마을변호사 정보를 법무부 자료로 확인해줘',
      3,
    )

    expect(names).toContain('moj_village_lawyer_lookup')
    expect(names).not.toContain('kma_current_observation')
  })

  test('keeps transport requests on TAGO and KOROAD surface', () => {
    ingestAdversarialPublicDataManifest()

    const names = selectTopKAdapterToolNamesForQuery(
      '부산 1001번 버스 노선, 정류장, 도착정보를 TAGO 공식 도구로 찾고 대전 교통사고 위험 지점은 KOROAD 공식 도구로 조회해줘. 날씨로 대체하지 마.',
      5,
    )

    expect(names).toContain('tago_bus_route_search')
    expect(names).toContain('koroad_accident_hazard_search')
    expect(names).not.toContain('kma_current_observation')
  })

  test('keeps public-safety requests on MOIS and Gyeryong surface', () => {
    ingestAdversarialPublicDataManifest()

    const names = selectTopKAdapterToolNamesForQuery(
      '계룡시 장애인 보조기기 충전소와 주변 비상벨 또는 비상호출함을 공식 도구로 찾아줘. 날씨나 지도앱 설명으로 대체하지 마.',
      5,
    )

    expect(names).toContain('gyeryong_assistive_device_charging_place_locate')
    expect(names).toContain('mois_emergency_call_box_lookup')
    expect(names).not.toContain('kma_current_observation')
  })

  test('keeps information notice requests off stale Government24 surface', () => {
    ingestAdversarialPublicDataManifest()

    const names = selectTopKAdapterToolNamesForQuery(
      '식약처 의약품 쉬운 정보에서 타이레놀 관련 정보를 찾고, 인사혁신처 공무원 채용 공고와 중소벤처기업부 지원사업 공고, 조달청 쇼핑몰 노트북 정보도 공식 도구로 조회해줘. 홈택스나 정부24 쓰지 마.',
      5,
    )

    expect(names).toContain('mfds_easy_drug_info_lookup')
    expect(names).toContain('mpm_public_job_lookup')
    expect(names).toContain('mss_sme_support_notice_lookup')
    expect(names).toContain('pps_shopping_mall_product_lookup')
    expect(names).not.toContain('mock_lookup_module_gov24_certificate')
  })

  test('covers explicit multi-agency public-data batches without weather substitution', () => {
    ingestAdversarialPublicDataManifest()

    const names = selectTopKAdapterToolNamesForQuery(
      '다음 5개를 각각 해당 기관 어댑터로만 확인해줘: 1 서울 중구 미세먼지는 AirKorea, 2 부산 사하구 마을변호사는 법무부, 3 계룡시 공지나 행사는 계룡시, 4 공정위 대기업집단 현황은 FTC, 5 조달청 물품분류는 PPS. 실패나 0건이면 그대로 말하고 다른 기관 자료로 대체하지 마.',
      5,
    )

    expect(names).toContain('airkorea_ctprvn_air_quality')
    expect(names).toContain('moj_village_lawyer_lookup')
    expect(names).toContain('pps_shopping_mall_product_lookup')
    expect(names).toContain('ftc_large_group_status')
    expect(names).not.toContain('kma_current_observation')
  })
})

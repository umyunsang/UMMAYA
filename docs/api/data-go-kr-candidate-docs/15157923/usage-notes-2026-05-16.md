# 15157923 광주광역시_광주버스정보

## Collection Status
- Source: <https://www.data.go.kr/data/15157923/openapi.do>
- Provider: 광주광역시
- Department: 대중교통과
- Category: 교통및물류 - 물류등기타
- Service type: REST
- Response format: JSON+XML
- Application status: approved.
- Usage-list evidence: `[승인] 광주광역시_광주버스정보`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`.
- Development quota: 100 calls/day per operation.
- Review policy: development account auto-approved, operation account auto-approved.
- Update cycle: real time.
- Spatial range: 광주광역시.
- License: no public-data usage restriction shown on data.go.kr.

## Saved Artifacts
- `data-go-kr-detail.html`: data.go.kr detail page snapshot.
- `data-go-kr-inline-swagger.json`: inline Swagger/OpenAPI metadata extracted from the data.go.kr detail page.
- `OPENAPI활용가이드_광주버스 v1.0.docx`: downloaded official guide.
- `OPENAPI활용가이드_광주버스 v1.0.docx.txt`: extracted text from the guide.
- `intake-record.json`: local intake metadata.

## Endpoint Summary
- Service URL: `https://apis.data.go.kr/6290000/gj_bis`
- Official guide callback URL: `http://apis.data.go.kr/6290000/gj_bis/`
- Supported schemes in portal Swagger: `https`, `http`

Operations:
- `GET /lineInfo`: BIS 노선 정보. Lists Gwangju bus routes, terminals, first/last run times, interval, and route type.
- `GET /stationInfo`: BIS 정류소 정보. Lists bus stops, ARS IDs, coordinates, English names, and next-stop direction.
- `GET /lineStationInfo`: BIS 노선-정류소 정보. Lists the stops served by one route.
- `GET /arriveInfo`: BIS 도착 정보. Lists arrival estimates for one bus stop.
- `GET /busLocationInfo`: BIS 노선 버스위치정보. Lists active vehicle positions for one route.

Common required request parameters:
- `serviceKey`: data.go.kr service key.
- `resultType`: response format. Use `json` for JSON responses or `xml` for XML responses.

Operation-specific required request parameters:
- `LINE_ID`: required for `lineStationInfo`; route ID. Official guide sample: `1`.
- `BUSSTOP_ID`: required for `arriveInfo`; bus-stop ID. Official guide sample: `2873`.
- `LINE_ID`: required for `busLocationInfo`; route ID. Official guide sample: `213`.

`lineInfo` response fields include:
- `RESULT.RESULT_CODE`, `RESULT.RESULT_MSG`: result status.
- `ROW_COUNT`: result row count.
- `LINE_LIST.ITEM.LINE_NUM`: list sequence number.
- `LINE_LIST.ITEM.LINE_ID`: route ID.
- `LINE_LIST.ITEM.LINE_NAME`: route name.
- `LINE_LIST.ITEM.DIR_UP_NAME`: start-point stop name.
- `LINE_LIST.ITEM.DIR_DOWN_NAME`: end-point stop name.
- `LINE_LIST.ITEM.FIRST_RUN_TIME`: first bus time.
- `LINE_LIST.ITEM.LAST_RUN_TIME`: last bus time.
- `LINE_LIST.ITEM.RUN_INTERVAL`: interval in minutes.
- `LINE_LIST.ITEM.LINE_KIND`: route type.

`stationInfo` response fields include:
- `STATION_LIST.ITEM.STATION_NUM`: list sequence number.
- `STATION_LIST.ITEM.BUSSTOP_ID`: bus-stop ID.
- `STATION_LIST.ITEM.BUSSTOP_NAME`: Korean bus-stop name.
- `STATION_LIST.ITEM.NAME_E`: English bus-stop name.
- `STATION_LIST.ITEM.LONGITUDE`, `STATION_LIST.ITEM.LATITUDE`: stop coordinates.
- `STATION_LIST.ITEM.ARS_ID`: public ARS stop code.
- `STATION_LIST.ITEM.NEXT_BUSSTOP`: next-stop direction.

`lineStationInfo` response fields include:
- `BUSSTOP_LIST.ITEM.BUSSTOP_NUM`: list sequence number.
- `BUSSTOP_LIST.ITEM.LINE_ID`, `BUSSTOP_LIST.ITEM.LINE_NAME`: route ID and name.
- `BUSSTOP_LIST.ITEM.BUSSTOP_ID`, `BUSSTOP_LIST.ITEM.BUSSTOP_NAME`: stop ID and name.
- `BUSSTOP_LIST.ITEM.ARS_ID`: public ARS stop code.
- `BUSSTOP_LIST.ITEM.LONGITUDE`, `BUSSTOP_LIST.ITEM.LATITUDE`: stop coordinates.
- `BUSSTOP_LIST.ITEM.RETURN_FLAG`: stop type. Guide values: `1` operating stop, `2` start point, `3` end point, `4` terminal/start marker.
- `BUSSTOP_LIST.ITEM.SEQ`: stop sequence on the route.

`arriveInfo` response fields include:
- `ARRIVE_LIST.ITEM.LINE_ID`, `ARRIVE_LIST.ITEM.LINE_NAME`, `ARRIVE_LIST.ITEM.SHORT_LINE_NAME`: route identifiers.
- `ARRIVE_LIST.ITEM.BUS_ID`: bus ID.
- `ARRIVE_LIST.ITEM.METRO_FLAG`: metro/area flag. Guide values: `0` Gwangju, `1` Naju, `2` Damyang, `3` Jangseong, `4` Hwasun.
- `ARRIVE_LIST.ITEM.CURR_STOP_ID`: current stop ID.
- `ARRIVE_LIST.ITEM.BUSSTOP_NAME`, `ARRIVE_LIST.ITEM.ENG_BUSSTOP_NAME`: current stop name.
- `ARRIVE_LIST.ITEM.REMAIN_MIN`: estimated minutes to arrival.
- `ARRIVE_LIST.ITEM.REMAIN_STOP`: remaining stop count.
- `ARRIVE_LIST.ITEM.DIR_START`, `ARRIVE_LIST.ITEM.DIR_END`: route direction endpoints.
- `ARRIVE_LIST.ITEM.LOW_BUS`: low-floor bus flag.
- `ARRIVE_LIST.ITEM.ARRIVE_FLAG`: soon-arriving flag. Guide values: `0` normal, `1` soon arriving.
- `ARRIVE_LIST.ITEM.LINE_KIND`: route type.

`busLocationInfo` response fields include:
- `BUSLOCATION_LIST.ITEM.NUM`: list sequence number.
- `BUSLOCATION_LIST.ITEM.LINE_ID`: route ID.
- `BUSLOCATION_LIST.ITEM.BUS_ID`: bus ID.
- `BUSLOCATION_LIST.ITEM.CURR_STOP_ID`: current stop ID.
- `BUSLOCATION_LIST.ITEM.CARNO`: vehicle plate number.
- `BUSLOCATION_LIST.ITEM.LOW_BUS`: low-floor bus flag.
- `BUSLOCATION_LIST.ITEM.CARDY`: vehicle type/internal field.
- `BUSLOCATION_LIST.ITEM.SEQ`: stop sequence.

## Adapter Notes
- Suggested primitive: `lookup`.
- Suggested tool name: `gwangju_bus_bis_lookup`.
- This is a read-only transit lookup adapter for Gwangju route, stop, arrival, and active-vehicle location data.
- The adapter should support at least five lookup modes matching the official operations: route catalog, stop catalog, route stops, stop arrivals, and route vehicle locations.
- For user-facing queries by stop or route name, resolve names through `stationInfo` and `lineInfo` before calling ID-specific endpoints.
- Preserve `REMAIN_MIN`, `REMAIN_STOP`, `ARRIVE_FLAG`, and the source operation name in outputs so the agent can explain arrival confidence and freshness.

## Curl Shape
```bash
curl --get 'https://apis.data.go.kr/6290000/gj_bis/lineInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'resultType=json'

curl --get 'https://apis.data.go.kr/6290000/gj_bis/stationInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'resultType=json'

curl --get 'https://apis.data.go.kr/6290000/gj_bis/lineStationInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'LINE_ID=1' \
  --data-urlencode 'resultType=json'

curl --get 'https://apis.data.go.kr/6290000/gj_bis/arriveInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'BUSSTOP_ID=2873' \
  --data-urlencode 'resultType=json'

curl --get 'https://apis.data.go.kr/6290000/gj_bis/busLocationInfo' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'LINE_ID=213' \
  --data-urlencode 'resultType=json'
```

## Implementation Cautions
- Do not persist or print the service key.
- Preserve exact official parameter casing: `serviceKey`, `resultType`, `LINE_ID`, and `BUSSTOP_ID`.
- The portal application form warns that this service contains location information. UMMAYA should expose it as public transit operational data and avoid treating vehicle-level fields as personal data.
- Daily development traffic is low at 100 calls/day per operation, so live fixture collection should be narrow and cached locally after direct curl validation.
- The extracted DOCX text contains a visible space in one rendered `stationInfo` sample URL; use the Swagger path `/stationInfo`, not `/ stationInfo`.

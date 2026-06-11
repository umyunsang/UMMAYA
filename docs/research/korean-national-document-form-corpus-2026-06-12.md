# Korean National Infrastructure Document Form Corpus

Date: 2026-06-12 KST

Purpose: build a source-grounded corpus for UMMAYA document-production real-use tests. This is not a representative single fixture. It is a first-pass inventory of document types and official/public attachment surfaces used across Korean national infrastructure, ministries, agencies, public institutions, local governments, and public utilities.

## Collection Rule

- Prefer official government, public-institution, or public-service portals.
- Record source pages and attachment names/formats, not copied form contents.
- Distinguish downloadable blank forms from online-only form screens.
- Treat forms that require applicant narrative, business plans, self-introductions, or proposal sections as Socratic-fill candidates: UMMAYA must ask for evidence before writing.
- Treat forms that require handwriting, color printing, signature, seal, or original submission as blocked for final submission automation but useful for extraction/render QA.

## Taxonomy

| Type | Korean surface | Typical owner | Main formats | Fill risk |
| --- | --- | --- | --- | --- |
| Statutory annex form | 별지서식, 별표서식 | 국가법령정보센터, every ministry | HWP, HWPX, PDF, DOC | structured fields, legal labels, protected cells |
| Civil application | 민원신청서, 신고서, 등록신청서 | 정부24, ministries, local governments | online form, HWP, PDF | identity, address, attachments, official-use boxes |
| Certificate/issuance request | 증명서 발급신청서, 사실증명 신청서 | Government24, passport, police, tax | online form, HWP, PDF | personal data and consent boundary |
| Tax form | 세무서식, 신고서, 신청서 | NTS, Law.go.kr, local tax offices | HWP, PDF | numeric precision, 법령서식 lineage |
| Social insurance form | 자격취득/상실, 보험료, 연금청구 | NHIS, NPS, 4-insurance, COMWEL | HTML, HWP/HWPX, PDF, TIFF | multi-agency combined fields |
| Labor petition/form | 진정서, 취업규칙 신고, 임금체불 확인 | MOEL/Labor portal | HWP, PDF, online | narrative allegations and evidence attachments |
| Welfare/health form | 복지급여 신청, 의료/장기요양 서식 | MOHW, Bokjiro, SSIS, NHIS | HWP, PDF | household/eligibility evidence |
| Passport/consular form | 여권발급, 동의서, 위임장, 사증 | MOFA/passport/embassy | PDF, HWP, DOC | print, color, handwritten/signature restrictions |
| Immigration form | 통합신청서, 사증발급신청서 | MOJ/HiKorea/MOFA | HWP, PDF | visa/status-specific branching |
| Procurement form | 우수제품, 공동상표, 입찰, 제품설명 | PPS, G2B | HWPX, HWP, XLSX | tables, specs, comparisons, attachments |
| Business support form | 사업신청서, 사업계획서 | MSS, K-Startup, Bizinfo, KOSMES | HWP, DOCX, PDF | narrative plans; must ask evidence |
| Public recruitment form | 응시원서, 자기소개서, 직무수행계획서 | ALIO, ministries, public institutions | HWP, PDF | narrative claims; must ask evidence |
| Education/licensing form | 학원, 교습소, 연구지원 신청 | MOE, education offices | HWP/HWPX, PDF | tables, legal fields, local variants |
| Police/safety form | 고소장, 교통허가, 신원진술 | Police 민원24, NFA | HWP, PDF, ZIP | incident narrative and legal sensitivity |
| Court/procedure form | 소송/가사/행정/집행 양식 | Court e-litigation/minwon | HWP, PDF | legal filing risk; strong handoff boundary |
| Rights/petition form | 고충민원, 이의신청, 정보공개 | ACRC, ePeople, open.go.kr | HWP, DOC, PDF, TXT | narrative facts, evidence, agency routing |
| Local government form | 민원편람, 조례/사업 신청 | Seoul, Busan, Gyeonggi, Jeju | HWP, HWPX, PDF, XLSX | locality-specific variants |
| Public utility form | 전기사용, 복지할인, 상수도 공사/신청 | KEPCO, water authorities | online, HWP, PDF | contract, billing, delegated consent |

## First-Pass Corpus

| ID | Domain | Source page | Evidence collected | Formats | UMMAYA test value |
| --- | --- | --- | --- | --- | --- |
| KR-FORM-001 | Statutory forms | https://www.law.go.kr/lsBylSc.do | National Law Information Center provides law annex/table/form search and save options including HWP/HWPX/PDF/DOC. | HWP, HWPX, PDF, DOC | canonical source for legal blank-form names and protected official fields |
| KR-FORM-002 | Statutory form API | https://www.data.go.kr/data/3069189/openapi.do | Data.go.kr describes Law Ministry annex/form data with unique ids, law links, title, document code, effective dates, and latest revision history. | XML metadata | corpus index seed; not a rendered form by itself |
| KR-FORM-003 | Tax forms | https://www.nts.go.kr/nts/ad/nf/nltFormatTotalApiList.do?mi= | NTS 전체서식 page shows tax forms are downloaded from Law.go.kr and lists 2,913 forms. | HWP/PDF via Law.go.kr | high-volume tax form corpus; legal lineage required |
| KR-FORM-004 | Information disclosure | https://www.moel.go.kr/info/opendata/guideInfoPop08.do | MOEL information-disclosure related forms include information request, oral request, third-party opinion, decision notice, delegation, objection forms. | HWP, TXT | common cross-agency right-to-information forms |
| KR-FORM-005 | Labor petition | https://www.moel.go.kr/local/gyeonggi/info/dataroom/view.do?bbs_seq=20251100039 | MOEL local office bundles complaint, complainant list, retirement-pension report, employment-rule report, unpaid-wage certificate request forms. | HWP | multi-form attachment bundle with legal narratives |
| KR-FORM-006 | Labor portal online | https://labor.moel.go.kr/minwonApply/minwonApply.do?searchGubun=2 | Labor Portal shows 민원서식명, 신청하기, 서식명, attachment list for petitions/reports. | online + attachment | TUI must distinguish online submission from local derivative docs |
| KR-FORM-007 | Health insurance forms | https://www.nhis.or.kr/static/html/wbdb/f/wbdbf.html | NHIS has a web 민원 서식 작성 surface and individual HTML forms. | HTML form pages | extraction from HTML form, not file mutation |
| KR-FORM-008 | NHIS/National Pension combined form | https://www.nhis.or.kr/static/html/wbdb/f/wbdbf0201.html | Four-insurance worker qualification loss form is rendered as an HTML statutory form with official-use cells. | HTML | multi-institution structured fields and official-use cells |
| KR-FORM-009 | NPS form list | https://www.nps.or.kr/pnsinfo/databbs/getOHAF0279M0List.do | NPS form list includes business qualification acquisition/loss, payment exception, change forms with examples/download/fax/email. | HWP, HWPX, PDF, TIFF | high-volume social-insurance form corpus |
| KR-FORM-010 | NPS individual form | https://www.nps.or.kr/pnsinfo/databbs/getOHAF0279M1.do?menuId=MN24000998&tmpltDataClsfCd=MAN&tmpltDataSn=152 | Payment exception/payment resume form page exposes HWP and PDF versions. | HWP, PDF | matched format pair for render/re-read comparison |
| KR-FORM-011 | COMWEL portal | https://devkeupyeo.comwel.or.kr/ | COMWEL mobile labor-welfare hub exposes 민원서식 팩스받기 across wage-total, industrial accident, employment insurance, wage claim, welfare, rehab, pension, objection. | fax form surface | form request channel, not simple file download |
| KR-FORM-012 | Passport forms | https://www.passport.go.kr/home/kor/applicationForm/index.do?menuPos=42 | Passport site lists passport issuance, legal guardian consent, objection, delegation, loss report, romanization change, emergency passport reason forms. | PDF, HWP | print/color/handwriting constraints must be modeled |
| KR-FORM-013 | Consular forms | https://www.mofa.go.kr/us-ko/brd/m_4522/view.do?seq=1197073 | MOFA embassy page lists emergency passport HWP and multiple passport/consular PDF forms. | HWP, PDF | embassy-specific form variants |
| KR-FORM-014 | Immigration/visa | https://www.law.go.kr/LSW/lsInfoP.do?lsId=008494 | Immigration Act Enforcement Rule links visa/stay statutory forms including 별지 제34호 forms. | HWP, PDF | law-governed visa/stay blank-form source |
| KR-FORM-015 | Visa application | https://uzb.mofa.go.kr/uz-ko/brd/m_8574/view.do?seq=1150101 | Embassy page provides visa application in HWP, DOC, PDF. | HWP, DOC, PDF | cross-format same form for conversion QA |
| KR-FORM-016 | Court forms | https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24 | Court e-litigation form collection lists family/procedure forms. | web list, HWP/PDF in court surfaces | legal-filing domain; likely handoff or draft-only |
| KR-FORM-017 | Police form library | https://minwon24.police.go.kr/cvlcpt/cvlcptTmpltGdList.do | Police 민원24 exposes downloadable 민원 서식 across traffic, investigation, life safety, guard, information, foreign affairs, audit, translations. | HWP, PDF, ZIP | legally sensitive reports and permits |
| KR-FORM-018 | Police service detail | https://minwon24.police.go.kr/cvlcpt/cvlcptGdInfo.do?cvlcptId=MW-010 | Bus-lane passage designation request page includes HWP/PDF statutory form files. | HWP, PDF | clean structured permit form |
| KR-FORM-019 | Public procurement | https://www.pps.go.kr/kor/content.do?key=00302 | PPS 우수제품 form page lists many HWPX/XLSX attachments: application guide, checklists, product description, specs, comparison tables, agreements. | HWPX, XLSX | style/table-heavy business-public form corpus |
| KR-FORM-020 | Public procurement legacy HWP | https://www.pps.go.kr/kor/content.do?key=00706 | PPS 공동상표 page lists HWP forms including 별지 제1호, 제2호, 제3호, 제10호, 제14호, 규격비교표. | HWP | HWP legacy procurement form corpus |
| KR-FORM-021 | Business-plan forms | https://www.mss.go.kr/site/smba/ex/bbs/View.do?bcIdx=1029124&cbIdx=310&parentSeq=1029124 | MSS business announcement provides 신사업창업사관학교 business-plan templates in HWP and DOCX. | HWP, DOCX | narrative business-plan Socratic fill |
| KR-FORM-022 | Business-plan portal | https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId=PBLN_000000000074174 | Bizinfo listing exposes 신청서 및 사업계획서(양식).hwp plus announcement PDF. | HWP, PDF | common SME-support application plan |
| KR-FORM-023 | Business-plan technical instruction | https://www.bizinfo.go.kr/cmm/fms/fileDown.do?atchFileId=FILE_000000000640508&fileSn=2 | Downloadable HWP shows application/business-plan writing rules including HWP, font, and style constraints. | HWP | style-preservation and instruction extraction |
| KR-FORM-024 | Public recruitment | https://www.alio.go.kr/mobile/information/informationRecruitDtl.do?seq=261935 | ALIO posting lists 채용공고.hwp, 응시원서 및 자기소개서 양식.hwp, 직무기술서, 개인정보 동의서. | HWP | self-introduction evidence loop |
| KR-FORM-025 | Public recruitment with job plan | https://www.alio.go.kr/information/informationRecruitDtl.do?e_date=2023.06.20&order=IDATE&pageNo=2&s_date=2022.11.20&seq=257240 | ALIO posting lists 지원서자기소개서직무수행계획서양식.hwp and privacy consent HWP. | HWP, PDF | self-introduction + job-performance-plan fill |
| KR-FORM-026 | Education ministry grant | https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=72761&boardSeq=105663&lev=0&m=020502&opType=N&page=1&s=moe&searchType=null&statusYN=W | MOE 2026 BK21 pilot announcement provides HWP/HWPX application forms. | HWP, HWPX | research/program proposal form |
| KR-FORM-027 | Education office licensing | https://dbedu.sen.go.kr/CMS/civilapp/civilapp01/civilapp0103/civilapp010301/1323424_2691.html | Seoul education office lists academy fee report, details, example, notice templates. | HWP, PDF | local education permit table-heavy forms |
| KR-FORM-028 | Welfare/health | https://www.mohw.go.kr/board.es?act=view&bid=0003&list_no=353083&mid=a10501010100&tag= | MOHW prescription proxy receipt application notice provides HWP statutory form. | HWP | health/privacy-sensitive simple form |
| KR-FORM-029 | Welfare service | https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00005438&wlfareInfoReldBztpCd=02 | Bokjiro local welfare service provides a long-term-care worker allowance application HWP. | HWP | local welfare application, eligibility evidence |
| KR-FORM-030 | Social-security institution | https://www.ssis.or.kr/lay1/bbs/S1T67C95/A/102/view.do?article_seq=127949 | SSIS 2026 research topic contest includes proposal form and privacy consent HWP files. | HWP, JPG | proposal narrative plus consent |
| KR-FORM-031 | Rights/petition | https://www.acrc.go.kr/menu.es?mid=a10201010100 | ACRC 고충민원 application guide provides downloadable HWP forms for complaint, representative appointment, representative selection/dismissal. | HWP | complaint narrative, representative authority |
| KR-FORM-032 | ePeople contest/claim | https://www.epeople.go.kr/nsf/Intro.html | ePeople claim flow says required objection form can be downloaded in Word, HWP, or PDF. | HWP, DOC, PDF | national petition/appeal multi-format |
| KR-FORM-033 | Local government Busan | https://www.busan.go.kr/minwon/manual/22751?curPage=45&srchBeginDt=&srchEndDt=&srchKey=&srchText= | Busan 민원편람 exposes environmental consulting guide and application HWP attachments. | HWP | local civil form with office-specific metadata |
| KR-FORM-034 | Local government Gyeonggi | https://www.gg.go.kr/bbs/boardView.do?bIdx=132024146&bcIdx=564&bsIdx=620&menuId=1623&page=1 | Gyeonggi 민원서식 page provides 사회환경교육기관 지정신청서 HWP and lists required supporting documents. | HWP | local permit + attached evidence set |
| KR-FORM-035 | Local government Seoul | https://cleanup.seoul.go.kr/cleanup/bbs/vscr.do?bbs.bbsSn=11720&bbsClCode=200&cpage=1&ctgryClCode=200&searchCode=&searchValue= | Seoul redevelopment portal provides homepage use/change application HWP. | HWP | city portal form variant |
| KR-FORM-036 | Public utility electricity | https://online.kepco.co.kr/CUM083D00 | KEPCO ON form library exposes electricity-use and power-transaction related forms. | online/download surface | utility contract/billing boundary |
| KR-FORM-037 | Public utility electricity guide | https://online.kepco.co.kr/MIM043D00 | KEPCO guide mentions electricity-use application and cases where consent recording/mobile consent can replace document submission. | online + consent | form-or-consent channel branching |
| KR-FORM-038 | Public utility water/public works | https://arisu.seoul.go.kr/home/sub?dsn=1704067100-022-140&menukey=7201&mode=view | Seoul Arisu announcement provides HWP/HWPX business participation and evaluation-submission forms. | HWP, HWPX | public-utility procurement form |

## Coverage Implications

1. HWP/HWPX is not optional for Korean national-infrastructure document work. It appears in statutory law, tax, labor, social insurance, procurement, recruitment, education, welfare, local government, and utility surfaces.
2. PDF is common but often paired with HWP/HWPX. PDF-only should not be assumed fillable; AcroForm detection is required.
3. DOC/DOCX appears in consular visa and business-plan variants; it should be supported but is not the dominant Korean public-form format.
4. XLSX appears where tabular procurement or model/spec data is the real submission surface.
5. Online HTML forms must be treated as separate from downloadable derivative-document editing.
6. Public recruitment and business-support applications prove that "blank form" includes narrative sections: 자기소개서, 직무수행계획서, 사업계획서, 제안서. These require a Socratic evidence loop and user approval before insertion.
7. Several official sources include style constraints: HWP-only, fixed pages, color/handwritten printing, fixed tables, protected official-use cells, or no table/heading deletion. These must become test assertions for render comparison and mutation safety.

## Initial Test Matrix

| Test family | Corpus IDs | Required behavior |
| --- | --- | --- |
| Structured blank-field fill | KR-FORM-001, 003, 009, 018, 033, 034 | extract slots; ask only missing required evidence; preserve official-use cells |
| Multi-format same-form diff | KR-FORM-010, 012, 015, 032 | compare HWP/PDF/DOC variants; preserve semantics |
| Table/style preservation | KR-FORM-019, 020, 026, 027, 038 | preserve fonts, table geometry, colors, labels, cell merges |
| Narrative Socratic fill | KR-FORM-021, 022, 024, 025, 030 | ask for evidence; create interim draft; insert only after approval |
| Online-only/handoff boundary | KR-FORM-006, 007, 011, 036, 037 | classify as online-channel/handoff, not local file edit |
| Legal/high-risk draft-only | KR-FORM-016, 017, 031 | draft or summarize only unless explicit evidence and legal-safe boundary are satisfied |

## Open Collection Gaps

- Download and hash a bounded fixture set from each corpus family after confirming license/reuse policy and file size.
- Add render baselines for HWPX/HWP/PDF/DOCX/XLSX representative files.
- Add institution-specific metadata: processing agency, submission channel, personal-data category, required attachments, signature/seal requirement, and whether handwritten submission is mandated.
- Separate public files that are form templates from notices, manuals, examples, and generated certificates.
- Add recurring official sources for Hometax/Wetax direct forms when an authenticated or official public download path can be verified without credentials.

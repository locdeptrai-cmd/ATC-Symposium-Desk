(function (root) {
  var ATC = root.ATC || (root.ATC = {});

  ATC.DOCS = {
    sms: "Annex 19 and Doc 9859 (Safety Management Manual)",
    frms: "Doc 9966 (Manual for the Oversight of FRMS) and the SMS framework in Doc 9859",
    atfm: "Doc 9971 (Manual on Collaborative ATFM)",
    pbn: "Doc 9613 (PBN Manual) and Doc 4444 (PANS-ATM)",
    swim: "the ICAO SWIM concept (Doc 9880) and the GANP / ASBU information-management threads",
    atco: "Doc 10056 (ATCO competency-based training and assessment)",
    atsep: "Doc 10057 (ATSEP competency-based training and assessment)",
    lpr: "Doc 9835 (Manual on the Implementation of ICAO Language Proficiency Requirements) and Annex 1",
    pans_atm: "Doc 4444 (PANS-ATM)",
    ganp: "Doc 9750 (Global Air Navigation Plan)",
    pans_trg: "Doc 9868 (PANS-Training)",
    acdm: "the ICAO A-CDM guidance and airport-ANSP-airline collaborative processes"
  };

  ATC.TOPIC_PACKS = {
    sms_frms: {
      id: "sms_frms",
      label: { vi: "SMS / FRMS", en: "SMS / FRMS" },
      keywords: [
        "frms", "fatigue", "mệt mỏi", "sms", "roster", "kíp trực", "lịch ca",
        "duty time", "time-in-position", "trực vị trí", "ca đêm", "night duty",
        "self-report", "fit for duty", "doc 9966", "doc 9859", "annex 19",
        "circular 47", "thông tư 47"
      ],
      glossary: ["FRMS", "SMS", "ATCO", "SPI", "CAPA"],
      gistEn:
        "whether fatigue risk management is embedded in the SMS, with predictive, proactive and reactive data — not treated as a standalone roster rule",
      gistVi:
        "quản lý mệt mỏi phải nằm trong SMS, dùng dữ liệu dự báo–chủ động–phản ứng, không chỉ chỉnh lịch kíp",
      points: [
        {
          en: "FRMS is a safety process inside SMS (policy, risk management, assurance, promotion), not a duty-time spreadsheet.",
          vi: "FRMS là quy trình an toàn trong SMS, không phải bảng giờ ca."
        },
        {
          en: "Use three data streams: predictive (roster biomathematics / planned duty), proactive (self-report, supervisor watch), reactive (occurrences, errors, sick leave).",
          vi: "Ba luồng dữ liệu: dự báo (lịch), chủ động (tự báo cáo, giám sát), phản ứng (sự cố, sai sót)."
        },
        {
          en: "Hard limits still apply: duty length, night duty, consecutive days, time-in-position and minimum rest. A green score does not override an unfit self-report.",
          vi: "Giới hạn cứng vẫn áp dụng; điểm xanh không thay thế báo cáo không đủ tỉnh táo."
        },
        {
          en: "Deviations need risk assessment, mitigation, approval and evidence — aligned with the State’s FRMS / SMS oversight.",
          vi: "Sai lệch phải có đánh giá rủi ro, biện pháp, phê duyệt và hồ sơ."
        }
      ],
      bodies: {
        delegate:
          "Fatigue controls must sit inside the SMS, not as a standalone roster rule. Changing the watch schedule without predictive, proactive and reactive FRMS data is a staffing tactic, not safety management. We treat roster design, time-in-position, night-duty limits, self-reporting and supervisory intervention as interacting barriers. Safety assurance then checks whether those barriers actually work. We are ready to share operational lessons with partners in the region, including how deviations are recorded and how just culture is protected in self-reports.",
        rapporteur:
          "In response: yes, fatigue management belongs in the SMS. The roster is one control, not the system. Our implementation uses planned-duty limits, live time-in-position discipline, fit-for-duty reporting, and post-event review. Where a night-duty or rest limit is stretched for operational continuity, that is a recorded deviation with mitigation — it is not a silent exception. I can take detailed questions on the indicators we monitor.",
        chair:
          "I thank the distinguished speaker for a precise question on FRMS and SMS. The point is noted: roster design is not by itself fatigue risk management. I invite the rapporteur — or the ANSP concerned — to answer on how predictive, proactive and reactive data are used. Please keep the reply to the SMS interface so we can stay on the agenda item.",
        interpreter:
          "Key pairings: fatigue risk management system (FRMS) — hệ thống quản lý rủi ro mệt mỏi; safety management system (SMS) — hệ thống quản lý an toàn; watch schedule / roster — lịch kíp trực; time-in-position — thời gian trực vị trí; predictive / proactive / reactive — dự báo / chủ động / phản ứng. Do not render FRMS as “chỉ chỉnh ca”."
      }
    },
    swim: {
      id: "swim",
      label: { vi: "SWIM", en: "SWIM" },
      keywords: [
        "swim", "fixm", "aixm", "wxxm", "information management", "data exchange",
        "thông tin toàn hệ thống", "trao đổi dữ liệu", "interoperability", "ff-ice"
      ],
      glossary: ["SWIM", "FIXM", "AIXM", "WXXM", "FF-ICE", "GANP"],
      gistEn:
        "a stepwise SWIM path: operational information services first, then wider interoperability — not a single big-bang platform",
      gistVi:
        "SWIM làm theo bước: dịch vụ thông tin đang khai thác trước, rồi mới liên thông rộng — không làm một lần",
      points: [
        {
          en: "SWIM is an information-management concept (services, governance, quality), not a single product purchase.",
          vi: "SWIM là khái niệm quản lý thông tin, không phải một phần mềm."
        },
        {
          en: "Start from exchanges that already have operational users: flight data, AIP/digital NOTAM, MET.",
          vi: "Bắt đầu từ trao đổi đã có người dùng khai thác: dữ liệu bay, AIP/NOTAM số, khí tượng."
        },
        {
          en: "Governance, identity and data quality decide whether partners will actually consume the service.",
          vi: "Quản trị, định danh và chất lượng dữ liệu quyết định đối tác có dùng thật hay không."
        },
        {
          en: "Align the roadmap with the GANP / ASBU information thread and with regional partners, not only with a local vendor timeline.",
          vi: "Lộ trình bám GANP/ASBU và đối tác khu vực, không chỉ lịch nhà thầu."
        }
      ],
      bodies: {
        delegate:
          "On SWIM, our position is stepwise and operational. We do not treat SWIM as one platform that must be finished before any information is shared. We start with exchanges that already have users — flight data, aeronautical information and MET — and we wrap them with service contracts, quality rules and access control. FIXM, AIXM and WXXM are the reference models; they are not a substitute for operational agreement. We are prepared to discuss a regional information-service catalogue rather than a single go-live date.",
        rapporteur:
          "The realistic first wave is not a full SWIM bus. It is a small set of information services with identified consumers: ATS units, the ATFM centre, AIS and airport partners. Timeline depends on data quality and letters of agreement, not only on middleware. I can show which services are in trial and which remain document-based.",
        chair:
          "Thank you. The question on SWIM sequencing is noted. I ask the presenter to distinguish the information-service roadmap from the vendor implementation plan, so the meeting does not mix a procurement milestone with an operational service. Floor to the rapporteur for a short reply on the first operational exchanges.",
        interpreter:
          "Keep SWIM untranslated as an acronym after the first expansion: system-wide information management. FIXM / AIXM / WXXM stay as acronyms. “Information service” — dịch vụ thông tin. “Interoperability” — khả năng liên thông. Avoid translating SWIM as “phần mềm chia sẻ”."
      }
    },
    pbn: {
      id: "pbn",
      label: { vi: "PBN", en: "PBN" },
      keywords: [
        "pbn", "rnav", "rnp", "cdo", "cco", "star", "sid", "continous descent",
        "continuous descent", "hạ độ cao", "leo cao", "dẫn đường dựa trên hiệu năng"
      ],
      glossary: ["PBN", "RNAV", "RNP", "CDO", "CCO", "STAR", "SID"],
      gistEn:
        "PBN procedures only deliver CCO/CDO benefits if ATFM, sector design and controller techniques protect the profile in peak traffic",
      gistVi:
        "PBN chỉ cho lợi ích CCO/CDO nếu ATFM, thiết kế khu vực và kỹ thuật kiểm soát giữ được biên độ khi cao điểm",
      points: [
        {
          en: "PBN is a specification (RNAV/RNP) plus a procedure design and an operational approval — not only a drawn track.",
          vi: "PBN gồm chỉ tiêu, thiết kế thủ tục và phê chuẩn khai thác — không chỉ vẽ đường."
        },
        {
          en: "CDO/CCO fail in the peak if vectoring and miles-in-trail become the default.",
          vi: "CDO/CCO gãy ở cao điểm nếu vector và giãn cách trở thành mặc định."
        },
        {
          en: "Publish where the profile will be broken (weather, runway change, go-around, military activity) so airlines can plan fuel honestly.",
          vi: "Công bố khi nào biên độ bị phá (thời tiết, đổi đường CHC, go-around, QS) để hãng tính nhiên liệu đúng."
        },
        {
          en: "Training must cover both the phraseology and the decision of when not to offer the full profile.",
          vi: "Huấn luyện phải gồm cả thuật ngữ và quyết định khi không cho full profile."
        }
      ],
      bodies: {
        delegate:
          "On PBN, our interest is the operational profile, not the chart count. RNAV and RNP STARs only reduce fuel and workload if we can protect continuous descent when demand allows, and if we are honest when we cannot. Peak-hour vectoring is sometimes required for sequencing; that must be a managed exception, not a silent collapse of the procedure. We support CCO/CDO where terrain, airspace and traffic permit, and we prefer published, predictable points where the profile may be discontinued.",
        rapporteur:
          "CDO and CCO are in the design. The operational question is when the TMA can keep the aircraft on the STAR without excessive vectoring. That depends on arrival-flow stability, runway configuration and the AMAN horizon. I will not claim a 100 percent CDO rate. I will report the conditions under which the profile is offered and the training we give when it is not.",
        chair:
          "The PBN item is specifically about protecting CCO and CDO, not about listing every published RNAV procedure. I ask speakers to address when the profile is offered, when it is discontinued, and how that is coordinated with ATFM. Floor to the unit for a concise operational reply.",
        interpreter:
          "PBN — performance-based navigation / dẫn đường dựa trên hiệu năng. CDO — continuous descent operations / khai thác hạ độ cao liên tục. CCO — continuous climb operations. STAR/SID remain acronyms. “Vectoring” — dẫn bằng ra-đa. Do not say “cleared ILS” unless that is in the source."
      }
    },
    atfm_capacity: {
      id: "atfm_capacity",
      label: { vi: "ATFM / năng lực", en: "ATFM / capacity" },
      keywords: [
        "atfm", "capacity", "năng lực", "delay", "slot", "flow", "luồng",
        "declared capacity", "throughput", "gdp", "miles-in-trail", "điều hòa"
      ],
      glossary: ["ATFM", "ATFMC", "A-CDM", "KPI", "ATS"],
      gistEn:
        "declared capacity must be based on ATCO staffing, sector design and CNS availability; ATFM then balances demand, it does not invent extra capacity",
      gistVi:
        "năng lực công bố dựa trên định biên ATCO, thiết kế khu vực và CNS; ATFM cân demand, không tạo thêm capacity",
      points: [
        {
          en: "Capacity is declared from the constraining resource: runway, TMA sector, ACC sector, or parking — not from a political target.",
          vi: "Năng lực công bố theo tài nguyên thắt: đường CHC, khu TMA, khu ACC hoặc sân đỗ."
        },
        {
          en: "ATFM measures (GDP, MIT, airborne holding) protect the safe rate; they do not replace a staffing or airspace problem.",
          vi: "Biện pháp ATFM bảo vệ nhịp an toàn; không thay thế thiếu người hoặc thiếu không phận."
        },
        {
          en: "Airport, ANSP and airlines must share the same demand picture (A-CDM / ATFM) or the delay just moves.",
          vi: "Sân bay, ANSP và hãng phải cùng một bức tranh demand, nếu không delay chỉ chuyển chỗ."
        },
        {
          en: "When demand exceeds capacity, reduce rate early. Late, uncoordinated restrictions cost more fuel and more ATC workload.",
          vi: "Demand vượt capacity thì giảm nhịp sớm. Hạn chế muộn, không hiệp đồng tốn nhiên liệu và tải ATC hơn."
        }
      ],
      bodies: {
        delegate:
          "On capacity and ATFM, we distinguish two questions that are often mixed. First: what rate can the ATS unit actually deliver with the staff, sectorisation and CNS of the day? That is declared capacity. Second: how do we balance demand against that rate with the airport and airspace users? That is ATFM. Raising a number on a slide does not raise capacity. We support early, collaborative measures through the ATFM centre rather than last-minute tactical holding that simply transfers delay into the TMA.",
        rapporteur:
          "When TMA delay grows, we do not first inflate declared capacity. We look at the constraint — runway, sector, weather, staffing — and we apply a flow measure that the airport and operators can see in time. Increasing the published rate without ATCO and CNS evidence would be a safety issue, not a customer-service win. I can walk through a peak-day example if the Chair allows.",
        chair:
          "I would like this discussion to keep declared capacity separate from ATFM measures. One is what the ATS system can safely deliver; the other is how demand is balanced. I give the floor to the ANSP to state the constraining resource on a typical peak day, then to ATFM for the measure used. Brief replies, please.",
        interpreter:
          "Declared capacity — năng lực công bố. ATFM — quản lý luồng không lưu. Ground delay programme — chương trình chậm dưới đất. Miles-in-trail — giãn cách theo hải lý. Do not translate “slot” as “khe thời gian sân bay” unless the source is airport slots; in ATFM it is a calculated take-off time."
      }
    },
    staffing: {
      id: "staffing",
      label: { vi: "Định biên / CBTA", en: "Staffing / CBTA" },
      keywords: [
        "staffing", "định biên", "cbta", "competency", "năng định", "ojt", "ojti",
        "atco", "atsep", "doc 10056", "doc 10057", "training", "huấn luyện",
        "endorsement", "licence", "license"
      ],
      glossary: ["ATCO", "ATSEP", "CBTA", "OJT", "OJTI"],
      gistEn:
        "traffic growth without a matching ATCO/ATSEP training pipeline is a capacity and safety risk; competency (Doc 10056/10057) is not a headcount only",
      gistVi:
        "tăng tàu bay mà không tăng pipeline ATCO/ATSEP là rủi ro năng lực và an toàn; năng lực (Doc 10056/10057) không chỉ là số người",
      points: [
        {
          en: "Established posts, unit endorsements and OJTI bandwidth are the real pipeline — not the recruitment advert.",
          vi: "Chỉ tiêu, năng định đơn vị và số OJTI mới là pipeline — không phải tin tuyển dụng."
        },
        {
          en: "Doc 10056 / 10057 shift the unit from hour-counting courses to observable competencies, including unusual situations.",
          vi: "Doc 10056/10057 đưa đơn vị từ đếm giờ học sang năng lực quan sát được, gồm tình huống bất thường."
        },
        {
          en: "If traffic grows faster than valid ratings, the safety response is to reduce declared capacity or sector opening, not to stretch time-in-position.",
          vi: "Tàu bay tăng nhanh hơn năng định thì phải giảm capacity hoặc số khu mở, không kéo dài trực vị trí."
        },
        {
          en: "ATSEP competency is part of the same ATM system: a surveillance or COM outage is an ATS capacity event.",
          vi: "Năng lực ATSEP cùng hệ thống ATM: mất giám sát/COM là sự kiện năng lực ATS."
        }
      ],
      bodies: {
        delegate:
          "On staffing, we will not pretend that traffic growth automatically produces controllers. The constraint is the training pipeline: selection, ab-initio, unit endorsement, and enough OJTIs who are themselves current. Competency-based training under Doc 10056 is how we know a person is ready, not the number of classroom hours. If demand exceeds the number of valid ratings, the operational answer is to manage capacity — not to extend time-in-position until fatigue and error rise together. The same logic applies to ATSEP under Doc 10057.",
        rapporteur:
          "The risk the speaker described is real: sector capacity rising on paper while endorsements lag. Our mitigation is a training plan tied to the roster and to OJTI availability, plus a rule that we do not open a sector we cannot staff to the required competency. I can provide the current training lead time without discussing individual personnel.",
        chair:
          "The staffing point is received. I ask that personnel numbers stay at the level of posts and training lead time — this is not a session for naming individuals. Floor to the unit to explain how competency, not only headcount, is used before a sector is opened.",
        interpreter:
          "Staffing levels — định biên. Unit endorsement — năng định đơn vị. CBTA — huấn luyện và đánh giá theo năng lực. OJTI — huấn luyện viên tại vị trí. ATCO / ATSEP remain acronyms. “Valid rating” — năng định còn hiệu lực."
      }
    },
    language: {
      id: "language",
      label: { vi: "Tiếng Anh ICAO", en: "Language proficiency" },
      keywords: [
        "language", "english", "proficiency", "level 4", "level 5", "icao english",
        "tiếng anh", "cấp độ 4", "doc 9835", "lpr", "phraseology", "plain language"
      ],
      glossary: ["LPR", "ATCO", "OJTI", "ICAO"],
      gistEn:
        "ICAO language proficiency is operational safety (Annex 1 / Doc 9835): test plus maintenance, including plain language in unusual situations",
      gistVi:
        "trình độ ngôn ngữ ICAO là an toàn khai thác (Annex 1 / Doc 9835): thi và duy trì, gồm plain language khi bất thường",
      points: [
        {
          en: "Level 4 is the minimum for licensing, not the operational ceiling for OJTI, supervisors and international coordination.",
          vi: "Level 4 là sàn cấp phép, không phải trần cho OJTI, ca trưởng và hiệp đồng quốc tế."
        },
        {
          en: "Phraseology covers the routine; unusual situations require plain language that is still concise and unambiguous.",
          vi: "Thuật ngữ phủ tình huống thường; bất thường cần plain language vẫn ngắn và không đa nghĩa."
        },
        {
          en: "Proficiency decays without use: units need a maintenance plan, not only a recency test date.",
          vi: "Năng lực ngôn ngữ giảm nếu không dùng: đơn vị cần kế hoạch duy trì, không chỉ ngày thi lại."
        },
        {
          en: "In ICAO courses, speak at a rate the room can follow; avoid idioms that will not survive interpretation.",
          vi: "Trong khóa ICAO, nói tốc độ phòng theo kịp; tránh thành ngữ chết khi phiên dịch."
        }
      ],
      bodies: {
        delegate:
          "Language proficiency is a safety requirement, not a training ornament. Annex 1 and Doc 9835 set Level 4 as the licensing minimum. For OJTIs, watch supervisors and positions that coordinate internationally, we aim higher because the failure mode is an unusual situation in plain language. We maintain proficiency through operational use, targeted refreshers and assessment — not through a single test date. In this room we will keep interventions short, standard and free of idiom so that interpretation remains accurate.",
        rapporteur:
          "After initial Level 4 we do not assume the skill is frozen. Maintenance is built from real traffic, unusual-situation practice, and periodic assessment. OJTI language is a separate risk: the instructor must demonstrate, not merely hold a certificate. I welcome examples from the course material if the Chair wishes to link this to the next exercise.",
        chair:
          "The language-proficiency question is relevant to both licensing and this course. I ask the faculty — or the unit — to answer on maintenance after Level 4, and on unusual-situation plain language, not on test-centre logistics. Interventions to two minutes, please, so interpretation can keep up.",
        interpreter:
          "Language proficiency requirements (LPR) — yêu cầu trình độ ngôn ngữ. ICAO Level 4 / Level 5 — giữ nguyên cấp độ. Phraseology — thuật ngữ chuẩn. Plain language — ngôn ngữ thường, không phải “tiếng lóng”. Do not invent radiotelephony (wilco, roger, cleared) in a conference interpretation unless it is in the source."
      }
    },
    cns: {
      id: "cns",
      label: { vi: "CNS / giám sát", en: "CNS / surveillance" },
      keywords: [
        "ads-b", "adsb", "radar", "mlat", "wam", "surveillance", "cns", "cpdlc",
        "giám sát", "ra-đa", "mode s", "navaid", "gbases", "gbas", "sbas"
      ],
      glossary: ["CNS", "ADS-B", "SSR", "PSR", "MLAT", "CPDLC", "ATSEP"],
      gistEn:
        "surveillance and COM performance set ATS separation and capacity; ATSEP competency and fallback procedures are part of the safety case",
      gistVi:
        "hiệu năng giám sát và liên lạc quyết định phân cách và năng lực ATS; năng lực ATSEP và phương án dự phòng nằm trong hồ sơ an toàn",
      points: [
        {
          en: "Separation minima and sector capacity assume a stated CNS performance. If that performance drops, the ATS method must change.",
          vi: "Phân cách và năng lực khu vực giả định một mức CNS. CNS giảm thì phương thức ATS phải đổi."
        },
        {
          en: "ADS-B / WAM complement radar; they do not remove the need for a fallback and for ATSEP response times.",
          vi: "ADS-B/WAM bổ sung ra-đa; không bỏ phương án dự phòng và thời gian xử lý ATSEP."
        },
        {
          en: "A surveillance outage is an ATFM and ATS event the same day — notify flow, reduce rate, apply the contingency LoA.",
          vi: "Mất giám sát là sự kiện ATFM và ATS trong ngày — báo luồng, giảm nhịp, áp LoA dự phòng."
        }
      ],
      bodies: {
        delegate:
          "CNS is not a background IT topic for this meeting. The separation standard and the declared capacity both assume a surveillance and communications performance. When that performance is degraded, the ATS unit must change method, and ATFM must change rate, the same day. We therefore treat ATSEP competency, spare equipment and published fallback procedures as safety barriers, not as workshop items. We are willing to share how an outage is handed from technical watch to the ops supervisor and then to flow management.",
        rapporteur:
          "I will answer in three layers: the nominal surveillance picture, the degraded mode, and the ATSEP response. Capacity numbers quoted earlier are for the nominal picture only. I will not defend those numbers in a fallback mode without a reduced-rate procedure.",
        chair:
          "Please keep CNS remarks tied to ATS method and capacity, not to a vendor feature list. I give the floor for a short explanation of the fallback when surveillance is degraded, including who informs ATFM.",
        interpreter:
          "Surveillance — giám sát. Fallback / contingency — phương án dự phòng. Outage — sự cố mất dịch vụ. ATSEP — nhân viên kỹ thuật an toàn không lưu. Keep ADS-B, MLAT, WAM, SSR, PSR as acronyms."
      }
    },
    safety: {
      id: "safety",
      label: { vi: "Just culture", en: "Just culture / SPI" },
      keywords: [
        "just culture", "văn hóa công bằng", "spi", "occurrence", "sự cố",
        "voluntary", "mandatory", "loss of separation", "runway incursion",
        "non-punitive", "blame"
      ],
      glossary: ["SMS", "SPI", "MOR", "CAPA", "ATS"],
      gistEn:
        "just culture protects honest reporting so the SMS can learn; it does not protect gross negligence — and SPIs must not become a blame scoreboard",
      gistVi:
        "văn hóa công bằng bảo vệ báo cáo trung thực để SMS học được; không bảo vệ cẩu thả thô — SPI không phải bảng quy trách nhiệm",
      points: [
        {
          en: "Without voluntary reports, the SMS only sees accidents and mandatory events — too late.",
          vi: "Không có báo cáo tự nguyện, SMS chỉ thấy tai nạn và sự cố bắt buộc — quá muộn."
        },
        {
          en: "Just culture is consistent, written, and applied by supervisors — not a slogan after an event.",
          vi: "Văn hóa công bằng phải viết rõ và ca trưởng áp dụng — không phải khẩu hiệu sau sự cố."
        },
        {
          en: "SPIs drive improvement. If they are used to rank and punish individuals, reporting dies.",
          vi: "SPI để cải tiến. Nếu dùng để xếp hạng và phạt cá nhân, báo cáo sẽ tắt."
        }
      ],
      bodies: {
        delegate:
          "Just culture is a condition for an SMS that actually learns. If a controller cannot file a voluntary report after a loss of separation without fearing automatic punishment, we will only receive the reports the law already forces. That is not safety assurance. At the same time, just culture is not a shield for gross negligence or wilful violations. The line must be written, trained and applied by supervisors. We also caution against turning SPIs into a personal scoreboard — that is the fastest way to kill reporting.",
        rapporteur:
          "In our process, a voluntary report opens a safety review, not a disciplinary file. Disciplinary process, if any, follows a separate test for wilful misconduct. I can describe the interface with the regulator without discussing a live case. SPIs stay at unit and process level in this presentation.",
        chair:
          "This is a sensitive item. I ask speakers not to cite live occurrences or name operational staff. The question is the interface between just culture and oversight. Floor to the safety office for a process answer, then one follow-up if time allows.",
        interpreter:
          "Just culture — văn hóa công bằng (không dịch “văn hóa dễ tính”). Voluntary report — báo cáo tự nguyện. Mandatory occurrence report — báo cáo sự cố bắt buộc. Gross negligence — cẩu thả thô. SPI — chỉ số hiệu suất an toàn."
      }
    },
    acdm: {
      id: "acdm",
      label: { vi: "A-CDM / AMAN", en: "A-CDM / AMAN" },
      keywords: [
        "a-cdm", "acdm", "aman", "dman", "tsat", "tobt", "target off-block",
        "cộng tác", "sân bay", "turnaround"
      ],
      glossary: ["A-CDM", "AMAN", "DMAN", "ATFM", "TMA"],
      gistEn:
        "A-CDM shares a single turnaround picture so ATS, airport and aircraft operators stop optimizing locally against each other",
      gistVi:
        "A-CDM dùng chung một bức tranh turnaround để ATS, sân bay và hãng không tối ưu cục bộ chống nhau",
      points: [
        {
          en: "TOBT/TSAT discipline only works if airlines update honestly and ATS/airport trust the stamp.",
          vi: "TOBT/TSAT chỉ chạy nếu hãng cập nhật thật và ATS/sân bay tin cái mốc đó."
        },
        {
          en: "AMAN needs a stable horizon; if ATFM and runway plans change every few minutes, the sequence is theatre.",
          vi: "AMAN cần chân trời ổn; ATFM và kế hoạch đường CHC đổi liên tục thì dãy chỉ là sân khấu."
        }
      ],
      bodies: {
        delegate:
          "A-CDM is useful to us only if it produces one shared clock: the aircraft operator, the airport and ATS looking at the same off-block and take-off targets. Local optimization — an early push that the TMA cannot take, or a hold at the holding point because TOBT was fiction — is what we are trying to stop. We support AMAN/DMAN where the runway plan is stable enough for the sequence to mean something.",
        rapporteur:
          "The operational test of A-CDM is whether TSAT is respected on a peak day, not whether the dashboard is pretty. I can report the current data sources and the remaining manual steps.",
        chair:
          "Please address A-CDM as a coordination process among ANSP, airport and operators. I will not take a vendor demonstration under this agenda item. Floor for a two-minute operational status.",
        interpreter:
          "A-CDM — ra quyết định cộng tác tại sân bay. TOBT — target off-block time. TSAT — target start-up approval time. AMAN/DMAN remain acronyms. “Turnaround” — vòng quay tàu bay dưới đất."
      }
    },
    general: {
      id: "general",
      label: { vi: "Chung", en: "General" },
      keywords: ["agenda", "chair", "floor", "intervention", "workshop", "course"],
      glossary: ["ATS", "ATM", "ICAO", "SMS"],
      gistEn: "a concise, on-agenda intervention in ICAO conference English",
      gistVi: "can thiệp ngắn, đúng agenda, bằng tiếng Anh hội nghị ICAO",
      points: [
        {
          en: "Address the Chair, state who you speak for, make one point, offer a fact or a next step, stop.",
          vi: "Thưa Chủ tọa, nêu danh nghĩa, nói một ý, đưa một sự kiện hoặc bước tiếp, dừng."
        },
        {
          en: "Do not use radiotelephony in the conference room.",
          vi: "Không dùng thuật ngữ vô tuyến trong phòng họp."
        }
      ],
      bodies: {
        delegate:
          "We thank the distinguished speaker. From an ATS provider perspective we support practical, implementable outcomes that improve safety and predictability. We will keep our point to the agenda item and we are ready to work with partners on the follow-up.",
        rapporteur:
          "Thank you for the question. I will answer within the scope of this session and take remaining detail to the break or to a written note if the Chair prefers.",
        chair:
          "Thank you. The point is noted. We have limited time. I will take this as the last intervention on this item unless a clarification is essential. The Secretariat will capture the action. We now move on.",
        interpreter:
          "Standard openers: Thank you, Chair — Kính thưa Chủ tọa. Distinguished delegate — quý đại biểu. The floor is yours — xin mời phát biểu. The point is noted — ý kiến đã được ghi nhận."
      }
    }
  };

  ATC.CHAIR_PHRASEOLOGY_BAN = [
    "cleared to land",
    "cleared for take-off",
    "cleared for takeoff",
    "roger",
    "wilco",
    "go ahead",
    "how do you read",
    "line up and wait",
    "taxi to",
    "contact tower",
    "squawk"
  ];
})(typeof globalThis !== "undefined" ? globalThis : this);

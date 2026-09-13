(function (root) {
  var ATC = root.ATC || (root.ATC = {});

  function affiliationEn(id) {
    var row = (ATC.AFFILIATIONS || []).filter(function (a) {
      return a.id === id;
    })[0];
    return row ? row.en : "Vietnam Air Traffic Management Corporation (VATM)";
  }

  function affiliationShort(id) {
    var map = {
      vatm: "VATM",
      norats: "VATM Northern Region",
      sorats: "VATM Southern Region",
      mirats: "VATM Middle Region",
      atfmc: "the VATM ATFM Centre",
      vnaic: "VNAIC",
      attech: "ATTECH",
      caav: "CAAV",
      delegation: "the Delegation of Viet Nam"
    };
    return map[id] || "VATM";
  }

  function chairName(opts) {
    return (opts && opts.chairTitle) || "Chair";
  }

  function contextTone(context) {
    if (context === "icao_course") {
      return {
        delegateOpen: "Thank you, {chair}. In the spirit of this ICAO course, and speaking from an ATS operations view,",
        courseClose: "We will take this back to the exercise and to unit procedures.",
        chairClose: "The faculty will pick this up in the next exercise if needed. Let us stay with the learning objective."
      };
    }
    if (context === "internal") {
      return {
        delegateOpen: "{chair}, from the unit,",
        courseClose: "We can follow up in the next ops briefing.",
        chairClose: "Action to the unit; we close this item."
      };
    }
    if (context === "workshop") {
      return {
        delegateOpen: "Thank you, {chair}. A short workshop point from {affiliationShort}:",
        courseClose: "Happy to continue this at the working table.",
        chairClose: "Please take remaining detail to the breakout. We keep the plenary moving."
      };
    }
    return {
      delegateOpen: "Thank you, {chair}. Speaking on behalf of {affiliationShort}.",
      courseClose: "We are ready to share operational lessons with partners in the region.",
      chairClose: "The Secretariat will note that point. We proceed."
    };
  }

  function fill(template, vars) {
    return String(template).replace(/\{(\w+)\}/g, function (_, k) {
      return vars[k] == null ? "" : vars[k];
    });
  }

  function wrapDelegate(body, vars, tone, intent) {
    var open = fill(tone.delegateOpen, vars);
    var ack =
      intent === "question_alternative" || intent === "question"
        ? "The question is well put."
        : intent === "rebuttal"
          ? "We hear the concern and we will answer it directly."
          : "We thank the distinguished speaker.";
    var close =
      vars.context === "internal"
        ? tone.courseClose
        : "Thank you, " + vars.chair + ".";
    var extra = vars.context === "conference" ? "" : tone.courseClose;
    return [open, ack, vars.heardLead, body, extra, close].filter(Boolean).join(" ");
  }

  function wrapRapporteur(body, vars, intent) {
    var open = "Thank you, " + vars.chair + ". I will take the question.";
    if (intent === "rebuttal") open = "Thank you, " + vars.chair + ". Allow me to respond to the point of rebuttal.";
    return [open, vars.heardLead, body, "I am available for one clarification if time permits."].filter(Boolean).join(" ");
  }

  function wrapChair(body, vars, tone, intent) {
    if (intent === "time_pressure") {
      return (
        "Colleagues, we have very little time on this item. I will take one last, short intervention, then we close. " +
        "Rapporteurs, please capture unanswered questions in writing. " +
        "We reconvene after the break. I thank you."
      );
    }
    return [body, tone.chairClose].join(" ");
  }

  function wrapInterpreter(pack, translation, original, direction) {
    var lines = [];
    lines.push("INTERPRETATION NOTE — stay with the term, do not add policy.");
    lines.push("");
    if (direction === "vi-en") {
      lines.push("EN (conference): " + translation);
      lines.push("Source VI: " + original);
    } else {
      lines.push("VI (for the delegation): " + translation);
      lines.push("Source EN: " + original);
    }
    lines.push("");
    lines.push(pack.bodies.interpreter);
    return lines.join("\n");
  }

  function viMirror(role, pack, vars) {
    var topic = pack.label.vi;
    if (role === "chair") {
      return (
        "Kính thưa quý đại biểu — điều hành phiên, không phải đài kiểm soát. " +
        "Ghi nhận ý kiến về " +
        topic +
        ". Mời đơn vị/báo cáo viên trả lời ngắn. Thư ký ghi nhận. Không dùng “cleared to land”, “roger”, “wilco” trong phòng họp."
      );
    }
    if (role === "interpreter") {
      return "Bám thuật ngữ " + topic + ". Không thêm lập trường. Đọc song ngữ các cụm trong glossary.";
    }
    if (role === "rapporteur") {
      return (
        "Trả lời Q&A: xác nhận vấn đề thuộc " +
        topic +
        ". Trả lời đúng phạm vi phiên, lấy số liệu đơn vị, mời hỏi làm rõ một câu nếu còn giờ."
      );
    }
    return (
      "Can thiệp đại biểu (" +
      vars.affiliationShort +
      "): cảm ơn Chủ tọa, nêu một ý về " +
      topic +
      ", lập trường vận hành, sẵn sàng chia sẻ bài học. Dừng."
    );
  }

  function trimToWindow(text, minW, maxW) {
    var words = String(text).trim().split(/\s+/);
    if (words.length <= maxW) {
      if (words.length >= minW) return words.join(" ");
      return text;
    }
    var cut = words.slice(0, maxW).join(" ");
    cut = cut.replace(/[,:;–—-]\s*$/, "");
    if (!/[.!?]$/.test(cut)) cut += ".";
    return cut;
  }

  function shortFromFull(full, pack, vars, role) {
    if (role === "chair") {
      return trimToWindow(full, 80, 150);
    }
    if (role === "interpreter") {
      return (
        pack.label.en +
        ": " +
        pack.gistEn +
        " / " +
        pack.gistVi
      );
    }
    var core = pack.bodies[role] || pack.bodies.delegate;
    var extras = (pack.points || [])
      .slice(0, 3)
      .map(function (p) {
        return p.en;
      })
      .join(" ");
    var open =
      role === "rapporteur"
        ? "Thank you, " + vars.chair + ". I will answer in about one minute."
        : "Thank you, " + vars.chair + ". Speaking on behalf of " + vars.affiliationShort + ".";
    var close = "We are ready to share operational lessons with partners in the region. Thank you, " + vars.chair + ".";
    if (role === "rapporteur") {
      close = "I remain available for one clarification. Thank you, " + vars.chair + ".";
    }
    return trimToWindow([open, core, extras, close].join(" "), 125, 200);
  }

  ATC.containsBannedChairTalk = function (text) {
    var t = String(text || "").toLowerCase();
    return (ATC.CHAIR_PHRASEOLOGY_BAN || []).some(function (p) {
      return t.indexOf(p) !== -1;
    });
  };

  ATC.buildLayers = function (opts) {
    opts = opts || {};
    var original = String(opts.text || "").trim();
    var listenLang = opts.listenLang || "auto";
    var translation =
      opts.translation ||
      ATC.translate(original, {
        source: listenLang === "auto" ? "auto" : listenLang,
        sessionTopic: opts.sessionTopic || "auto"
      });
    var topicId = translation.topic.id;
    var pack = ATC.TOPIC_PACKS[topicId] || ATC.TOPIC_PACKS.general;
    var intent = ATC.detectIntent(original);
    var role = opts.role || "delegate";
    var context = opts.context || "conference";
    var heardLead = "";
    if (listenLang === "en" && role !== "chair" && role !== "interpreter" && typeof ATC.heardBrief === "function") {
      heardLead = ATC.heardBrief(original);
    }
    var vars = {
      chair: chairName(opts),
      affiliation: affiliationEn(opts.affiliation),
      affiliationShort: affiliationShort(opts.affiliation),
      context: context,
      heardLead: heardLead
    };
    var tone = contextTone(context);
    var body = pack.bodies[role] || pack.bodies.delegate;
    var statementEn;
    if (role === "delegate") statementEn = wrapDelegate(body, vars, tone, intent);
    else if (role === "rapporteur") statementEn = wrapRapporteur(body, vars, intent);
    else if (role === "chair") statementEn = wrapChair(body, vars, tone, intent);
    else statementEn = wrapInterpreter(pack, translation.text, original, translation.source === "vi" ? "vi-en" : "en-vi");

    if (role === "chair" && ATC.containsBannedChairTalk(statementEn)) {
      statementEn =
        "Thank you. The point is noted. I give the floor for a short reply. We will not use radiotelephony in this room. The Secretariat will record the action.";
    }

    var shortEn = role === "interpreter" ? statementEn : shortFromFull(statementEn, pack, vars, role);
    var statementVi = viMirror(role, pack, vars);
    var shortVi =
      role === "chair"
        ? "Ghi nhận. Mời trả lời ngắn. Thư ký ghi. Chuyển mục."
        : role === "interpreter"
          ? pack.gistVi
          : "Cảm ơn Chủ tọa. Một ý: " + pack.gistVi + " Sẵn sàng chia sẻ. Xin hết.";

    var points = (pack.points || []).map(function (p) {
      return { en: p.en, vi: p.vi };
    });

    var transHeading =
      translation.source === "vi"
        ? "Bản dịch chuyên ngành (VI → EN hội nghị)"
        : "Bản dịch chuyên ngành (EN → VI để hiểu)";

    var caution = null;
    if (role === "chair") {
      caution = "Chủ tọa điều hành phiên: ghi nhận, chia sàn, giữ giờ. Không dùng phraseology đài kiểm soát.";
    } else if (translation.usedGist) {
      caution =
        "Một số câu chưa khớp cụm chuyên ngành — vẫn giữ nội dung nghe được và dịch các từ/cụm đã có.";
    } else if (translation.topic.mismatch) {
      caution =
        "Phiên đang chọn " +
        (opts.sessionTopic || "") +
        " nhưng nội dung nghiêng về " +
        pack.label.vi +
        ". Câu đáp theo nội dung nghe được.";
    }

    return {
      role: role,
      context: context,
      intent: intent,
      topic: { id: topicId, label: pack.label },
      translation: {
        heading: transHeading,
        direction: translation.source + "→" + translation.target,
        method: translation.method,
        text: translation.text,
        original: original
      },
      statement: { en: statementEn, vi: statementVi },
      short: {
        en: shortEn,
        vi: shortVi,
        words: ATC.countWords(shortEn),
        seconds: ATC.estimateSeconds(shortEn)
      },
      points: points,
      glossary: ATC.glossaryForTopic(topicId, original + " " + statementEn),
      docs: docsFor(topicId),
      caution: caution
    };
  };

  function docsFor(topicId) {
    var d = ATC.DOCS || {};
    var map = {
      sms_frms: [d.sms, d.frms],
      swim: [d.swim, d.ganp],
      pbn: [d.pbn, d.pans_atm],
      atfm_capacity: [d.atfm, d.pans_atm],
      staffing: [d.atco, d.atsep, d.pans_trg],
      language: [d.lpr],
      cns: [d.pans_atm, d.atsep],
      safety: [d.sms],
      acdm: [d.acdm, d.atfm],
      general: [d.pans_atm, d.sms]
    };
    return map[topicId] || map.general;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);

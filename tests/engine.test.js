"use strict";
/* Standalone suite — paths are ../web/js, not the ERP tree. */

var path = require("path");
var assert = require("assert");

["glossary.js", "topics.js", "lexicon.js", "dict-en-vi.js", "library-data.js", "library.js", "translate.js", "replies.js", "speech-repair.js"].forEach(function (f) {
  require(path.join(__dirname, "..", "web", "js", f));
});

var ATC = globalThis.ATC;
assert.ok(ATC, "ATC namespace");
assert.ok(ATC.TERMS.length > 20, "glossary loaded");
assert.ok(ATC.TOPIC_PACKS.sms_frms, "topics loaded");

var FRMS_Q =
  "Xin hỏi đơn vị đã đưa quản lý mệt mỏi vào SMS chưa, hay mới chỉ chỉnh lịch kíp trực?";

var tr = ATC.translate(FRMS_Q, { source: "vi" });
assert.strictEqual(tr.source, "vi");
assert.ok(/fatigue/i.test(tr.text), "EN translation mentions fatigue: " + tr.text);
assert.ok(/SMS/i.test(tr.text), "EN translation keeps SMS: " + tr.text);
assert.ok(!/Xin hỏi/.test(tr.text), "should not leave Vietnamese opener");
assert.ok(!/[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/.test(tr.text), "no leftover Vietnamese: " + tr.text);
assert.ok(!/\b(đã|chưa)\b/.test(tr.text), "no leftover particles: " + tr.text);
assert.strictEqual(tr.topic.id, "sms_frms", "topic is FRMS/SMS");

var delegate = ATC.buildLayers({
  text: FRMS_Q,
  listenLang: "vi",
  role: "delegate",
  context: "conference",
  affiliation: "sorats",
  sessionTopic: "auto"
});
assert.ok(/^Thank you, Chair/i.test(delegate.statement.en), delegate.statement.en.slice(0, 80));
assert.ok(/Southern Region/i.test(delegate.statement.en), "affiliation in statement");
assert.ok(/SMS/i.test(delegate.statement.en), "SMS in reply");
assert.ok(/FRMS|fatigue/i.test(delegate.statement.en));
assert.ok(/ready to share operational lessons/i.test(delegate.statement.en));
assert.ok(delegate.short.words >= 120, "60-90s intervention length: " + delegate.short.words + " words");
assert.ok(delegate.short.seconds >= 55, "duration ~60s: " + delegate.short.seconds + "s");
assert.ok(delegate.glossary.some(function (g) { return g.abbr === "FRMS"; }));

var chair = ATC.buildLayers({
  text: FRMS_Q,
  listenLang: "vi",
  role: "chair",
  context: "conference",
  affiliation: "sorats"
});
assert.ok(!ATC.containsBannedChairTalk(chair.statement.en), chair.statement.en);
assert.ok(!/cleared to land/i.test(chair.statement.en));
assert.ok(/floor|noted|invite|rapporteur|Secretariat/i.test(chair.statement.en), chair.statement.en);

var interp = ATC.buildLayers({
  text: FRMS_Q,
  listenLang: "vi",
  role: "interpreter",
  context: "conference",
  affiliation: "vatm"
});
assert.ok(/do not add policy/i.test(interp.statement.en));
assert.ok(/lịch kíp trực/i.test(interp.statement.en));

var swim = ATC.buildLayers({
  text: "What is the realistic timeline for SWIM implementation at the ANSP?",
  listenLang: "en",
  role: "delegate",
  context: "workshop",
  affiliation: "atfmc"
});
assert.strictEqual(swim.topic.id, "swim");
assert.ok(/SWIM/i.test(swim.translation.text), swim.translation.text);
assert.ok(/[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(swim.translation.text), "EN→VI should contain Vietnamese: " + swim.translation.text);

var hall = ATC.translate(
  "Ladies and gentlemen, today we will discuss safety and capacity in the TMA.",
  { source: "en" }
);
assert.ok(/[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(hall.text), "hall EN→VI: " + hall.text);
assert.ok(!/^Diễn giả nêu vấn đề/.test(hall.text), "must not replace speech with a topic gist: " + hall.text);
assert.ok(/thưa quý vị/i.test(hall.text), hall.text);
assert.ok(/an toàn/.test(hall.text), hall.text);
assert.ok(/chúng tôi/.test(hall.text), hall.text);
assert.ok(!/tôtôi|đổtôi|đư vào/.test(hall.text), hall.text);

var swimText = ATC.translate(
  "What is the realistic timeline for SWIM implementation at the ANSP, and which information exchanges will be operational first — flight, aeronautical or weather data?",
  { source: "en" }
);
assert.ok(/lộ trình|triển khai SWIM|trao đổi thông tin/i.test(swimText.text), swimText.text);
assert.ok(/đưa vào/.test(swimText.text) || /khai thác trước/.test(swimText.text), swimText.text);
assert.ok(!/thiếc|cỏ khô/.test(swimText.text), swimText.text);
assert.ok(/TMA|khu vực/i.test(hall.text), "keep TMA or its Vietnamese term: " + hall.text);

assert.ok(ATC.EN_VI_DICT && Object.keys(ATC.EN_VI_DICT).length > 5000, "general EN-VI dictionary loaded");

var just = ATC.translate(
  "If a controller files a voluntary report after a loss of separation, how do you protect just culture while still meeting the regulator’s enforcement expectations?",
  { source: "en" }
);
assert.ok(/kiểm soát viên/.test(just.text), just.text);
assert.ok(/báo cáo tự nguyện/.test(just.text), just.text);
assert.ok(/mất phân cách/.test(just.text), just.text);
assert.ok(/văn hóa công bằng/.test(just.text), just.text);
assert.ok(!/bộ điều khiển/.test(just.text), just.text);
assert.ok(!/cuộc mít tinh/.test(just.text), just.text);
assert.ok(!/sự làm sạch/.test(just.text), just.text);

var timeQ = ATC.buildLayers({
  text: "We have three remaining questions and only four minutes before the coffee break. How should the Chair close this item?",
  listenLang: "en",
  role: "chair",
  context: "conference",
  affiliation: "vatm"
});
assert.strictEqual(timeQ.intent, "time_pressure");
assert.ok(/little time|last/i.test(timeQ.statement.en));

var course = ATC.buildLayers({
  text: "How does the unit maintain ICAO language proficiency for ATCOs after initial Level 4?",
  listenLang: "en",
  role: "delegate",
  context: "icao_course",
  affiliation: "norats"
});
assert.strictEqual(course.topic.id, "language");
assert.ok(/ICAO course|Doc 9835|Level 4/i.test(course.statement.en));

var split = ATC.splitUtterances(
  "Ladies and gentlemen. Today we will discuss safety. Thank you, Chair."
);
assert.strictEqual(split.length, 3, "split three sentences: " + JSON.stringify(split));
assert.ok(/^Ladies/.test(split[0]), split[0]);
assert.ok(/safety/.test(split[1]), split[1]);

var repaired = ATC.repairHeard("the unit must put f r m s inside s m s not just the roster", "en");
assert.ok(/\bFRMS\b/.test(repaired.text), repaired.text);
assert.ok(/\bSMS\b/.test(repaired.text), repaired.text);
var picked = ATC.pickHeardAlternative([
  { transcript: "the farms inside the sms", confidence: 0.4 },
  { transcript: "the FRMS inside the SMS", confidence: 0.35 }
]);
assert.ok(picked && /FRMS/.test(picked.text), JSON.stringify(picked));
assert.strictEqual(ATC.mergeHeardOverlap("fatigue risk management", "risk management in the SMS"), "fatigue risk management in the SMS");
var tapeGlued = ATC.repairHeard("uh um insidetheSMS not just the roster shh", "en", { tape: true });
assert.ok(/inside the SMS/i.test(tapeGlued.text), tapeGlued.text);
assert.ok(!/\buh\b/i.test(tapeGlued.text), tapeGlued.text);
var tapeDup = ATC.repairHeard("FRMS inside inside the SMS", "en", { tape: true });
assert.ok(!/inside inside/i.test(tapeDup.text), tapeDup.text);
var tapeAbbr = ATC.repairHeard("the unit must put FRMSinside the SMS", "en", { tape: true });
assert.ok(/\bFRMS\b/.test(tapeAbbr.text) && /inside/i.test(tapeAbbr.text), tapeAbbr.text);
var tapeStutter = ATC.repairHeard("the the the FRMS inside the SMS", "en", { tape: true });
assert.ok(!/the the/i.test(tapeStutter.text), tapeStutter.text);
assert.ok(/\bFRMS\b/.test(tapeStutter.text), tapeStutter.text);
var noisyScript = ATC.buildLayers({
  text: "What is the realistic timeline for SWIM implementation at the ANSP?",
  listenLang: "en",
  role: "delegate",
  context: "workshop",
  affiliation: "atfmc"
});
assert.ok(/point on the floor concerns/i.test(noisyScript.statement.en), noisyScript.statement.en);
assert.ok(/SWIM/i.test(noisyScript.statement.en), noisyScript.statement.en);

var pidginSrc =
  "Cooperation, collaboration and standardization over decades, ICAO has ensured that this framework contributes";
var pidgin = ATC.translate(pidginSrc, { source: "en", unit: "sentence" });
assert.ok(!/nội dung này/.test(pidgin.text), "no demonstrative unigram mix: " + pidgin.text);
assert.ok(!/điều đó/.test(pidgin.text), "no that→điều đó mix: " + pidgin.text);
assert.ok(pidgin.original === pidginSrc, "English original stays on the source field");
assert.ok(/hợp tác|qua nhiều thập kỷ|ICAO/.test(pidgin.text), pidgin.text);

var justSent = ATC.translate(
  "If a controller files a voluntary report after a loss of separation, how do you protect just culture while still meeting the regulator’s enforcement expectations?",
  { source: "en", unit: "sentence" }
);
assert.ok(/văn hóa công bằng/.test(justSent.text), justSent.text);
assert.ok(/báo cáo tự nguyện/.test(justSent.text), justSent.text);
assert.ok(!/nội dung này|điều đó/.test(justSent.text), justSent.text);

console.log("engine.test.js: all assertions passed");
console.log("  FRMS translation:", tr.text);
console.log("  Delegate words:", delegate.short.words, "~" + delegate.short.seconds + "s");
console.log("  Chair sample:", chair.statement.en.slice(0, 120) + "...");

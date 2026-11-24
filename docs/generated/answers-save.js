// Saves a handover page's answers (radio picks, "Something else" text, to-do ticks and the finished reply)
// to the artifact's shared database as they change, so they survive a broken copy button or a closed tab.
// It adds nothing to the page's own logic: it only reads the same inputs the page's reply() reads.
(function () {
  var DOC = "answers/current";
  var KEY = "house-rules-answers:" + (document.title || "page");
  var st = document.createElement("p");
  st.className = "status";
  st.id = "savest";
  st.textContent = "Saving is starting…";
  var host = document.querySelector(".reply");
  if (host) host.appendChild(st);

  function say(t) { st.textContent = t; }

  function read() {
    var picks = {}, own = {}, ticks = [];
    document.querySelectorAll("#qs input[type=radio]:checked").forEach(function (r) { picks[r.name] = r.value; });
    document.querySelectorAll("#qs .owntext").forEach(function (t, i) {
      var q = t.closest("fieldset");
      var name = q && q.querySelector("input[type=radio]") ? q.querySelector("input[type=radio]").name : String(i);
      if (t.value) own[name] = t.value;
    });
    document.querySelectorAll("#todo input[type=checkbox]").forEach(function (c) { ticks.push(c.checked); });
    var out = document.getElementById("out");
    return { picks: picks, own: own, ticks: ticks, reply: out ? out.textContent : "", savedAt: new Date().toISOString() };
  }

  function apply(d) {
    if (!d) return;
    var typed = Array.prototype.some.call(document.querySelectorAll("#qs .owntext"), function (t) { return t.value; }) ||
      document.querySelector("#qs input[type=radio]:checked");
    if (typed) return; // this view already has answers: never overwrite what the person just did
    Object.keys(d.picks || {}).forEach(function (n) {
      var r = document.querySelector('#qs input[type=radio][name="' + n + '"][value="' + d.picks[n] + '"]');
      if (r) r.checked = true;
    });
    Object.keys(d.own || {}).forEach(function (n) {
      var f = document.querySelector('#qs input[type=radio][name="' + n + '"]');
      var t = f && f.closest("fieldset") && f.closest("fieldset").querySelector(".owntext");
      if (t) t.value = d.own[n];
    });
    (d.ticks || []).forEach(function (v, i) {
      var c = document.querySelectorAll("#todo input[type=checkbox]")[i];
      if (c) c.checked = !!v;
    });
    document.dispatchEvent(new Event("change", { bubbles: true }));
  }

  var db = null, timer = null, busy = false, again = false;

  function mirror(d) { try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) { /* storage may be blocked */ } }

  function flush() {
    var d = read();
    mirror(d);
    if (!db) { say("Kept in this browser only: saving to the artifact is not available here."); return; }
    if (busy) { again = true; return; }
    busy = true;
    db.doc(DOC).set(d).then(function () {
      say("Saved " + new Date().toLocaleTimeString() + ".");
    }).catch(function (e) {
      say("NOT saved to the artifact (" + ((e && (e.code || e.message)) || "unknown error") + "). Your answers are still on this page.");
    }).then(function () {
      busy = false;
      if (again) { again = false; flush(); }
    });
  }

  function queue() { clearTimeout(timer); timer = setTimeout(flush, 500); }
  document.addEventListener("change", queue);
  document.addEventListener("input", queue);

  var give = setTimeout(function () {
    if (!db) say("Kept in this browser only: saving to the artifact is not available here.");
  }, 10000);

  if (window.claude && window.claude.use) {
    window.claude.use("db").then(function (d) {
      clearTimeout(give);
      db = d;
      if (!db) { say("Kept in this browser only: saving to the artifact is not available here."); return; }
      return db.doc(DOC).get().then(function (s) {
        if (s.exists) { apply(s.data()); say("Restored your saved answers."); }
        else { say("Nothing saved yet. Your answers save as you pick them."); }
        if (read().reply && (Object.keys(read().picks).length || Object.keys(read().own).length)) flush();
      });
    }).catch(function (e) { say("Could not reach saved answers (" + ((e && (e.code || e.message)) || "unknown error") + ")."); });
  } else {
    say("Kept in this browser only: saving to the artifact is not available here.");
  }
})();

// Mesa de poker em pixel art: feltro, 2–10 lugares numa elipse (o meu em baixo), cartas comunitárias, pote e side pots,
// as minhas cartas em grande, barra de ações com temporizador do servidor e registo curto. Só desenha o que o servidor
// manda: as cartas fechadas dos outros nunca existem aqui (só o verso) até haver showdown.
import { el } from "../../dom.js";
import { t } from "../../../services/i18n.js";
import { toast } from "../../toast.js";
import { errorText } from "../../../services/api.js";
import { motion, reducedMotion } from "../../../services/motion.js";
import { cardEl, cardSlot, normCard } from "./cards.js";
import { chips, chipImg, fmt } from "./chips.js";
import { ACTION } from "./live.js";

const TURN_SECONDS = 30;
const TONES = ["bg-team-0", "bg-team-1", "bg-team-2", "bg-team-3", "bg-team-4", "bg-team-5", "bg-team-6", "bg-team-7"];
const tone = (seed) => { let h = 0; for (const c of String(seed ?? "")) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h % 8; };
const avatar = (seed) => el("span", { class: `pk-av ${TONES[tone(seed)]}` }, el("img", { class: "sprite", src: "/assets/sprites/icons/profile.png", width: 24, height: 24, alt: "" }));

// mountTable(host, live, {onSit(seat), say(text)}) -> {update(), destroy()}
export function mountTable(host, live, { onSit, say = () => {} } = {}) {
  const felt = el("div", { class: "pk-felt", "aria-hidden": "true" });
  const board = el("div", { class: "pk-board", role: "group", "aria-label": t("poker.board") });
  const potEl = el("div", { class: "pk-pot", role: "status" });
  const center = el("div", { class: "pk-center" }, board, potEl);
  const seatsLayer = el("div", { class: "pk-seats" });
  const fly = el("div", { class: "pk-fly", "aria-hidden": "true" });
  const tableEl = el("div", { class: "pk-table" }, felt, center, seatsLayer, fly);
  const timerBanner = el("p", { class: "pk-turnline", role: "status", "aria-live": "polite" });
  const meCards = el("div", { class: "pk-hole" });
  const meInfo = el("p", { class: "pk-hole-info" });
  const bar = el("div", { class: "pk-actions" });
  const log = el("ol", { class: "pk-log", "aria-label": t("poker.log") });
  const root = el("div", { class: "pk-root" }, tableEl, timerBanner, el("div", { class: "pk-me" }, meCards, meInfo), bar, log);
  host.replaceChildren(root);

  let busy = false, raiseTo = null, shownBoard = 0, lastHandId = null, toastedHand = null;
  const logLines = [];
  const afterRender = [];

  // ---------- auxiliares ----------
  const nameOf = (uid) => live.snap()?.seats?.find((s) => s.user_id === uid)?.display_name ?? "?";
  const mySeat = () => live.snap()?.me?.seat ?? null;
  const remaining = () => {
    const h = live.snap()?.hand;
    const dl = h?.deadline ? Date.parse(h.deadline) : null;
    return dl ? Math.max(0, (dl - (Date.now() + live.offset())) / 1000) : null;
  };

  function pushLog(text) {
    logLines.push(text);
    while (logLines.length > 6) logLines.shift();
    log.replaceChildren(...logLines.map((x) => el("li", {}, x)));
  }

  // ---------- lugares ----------
  function seatPos(rel, n) {
    const a = (Math.PI / 2) + (rel * 2 * Math.PI) / n; // 90° = em baixo; cresce no sentido horário do ecrã
    return { x: 50 + 38 * Math.cos(a), y: 50 + 42 * Math.sin(a), cx: Math.cos(a), cy: Math.sin(a) };
  }

  function seatNode(s, i, n, snap) {
    const hand = snap.hand;
    const rel = (i - (mySeat() ?? 0) + n) % n;
    const pos = seatPos(rel, n);
    const empty = !s.user_id;
    const mine = s.user_id && s.user_id === snap.me?.user_id;
    const inHand = !empty && !!s.in_hand && !s.folded;
    const turn = hand?.to_act === s.seat && hand?.street !== "showdown";
    const node = el("div", { class: `pk-seat${empty ? " is-empty" : ""}${mine ? " is-me" : ""}${turn ? " is-turn" : ""}${s.folded ? " is-folded" : ""}${s.status && s.status !== "sitting" ? " is-away" : ""}`, "data-seat": String(s.seat) });
    node.style.left = `${pos.x}%`; node.style.top = `${pos.y}%`;
    if (empty) {
      const canSit = mySeat() == null && snap.me?.can_sit !== false && onSit;
      node.append(canSit
        ? el("button", { type: "button", class: "pk-sit", onclick: () => onSit(s.seat), "aria-label": t("poker.sit_at", { n: s.seat + 1 }) }, el("span", { "aria-hidden": "true" }, "+"), el("small", {}, t("poker.sit")))
        : el("span", { class: "pk-empty", "aria-label": t("poker.empty_seat", { n: s.seat + 1 }) }, "·"));
      return node;
    }
    // cartas dos outros: só as que vieram num showdown (até começar a mão seguinte)
    const rev = live.revealed().get(s.user_id);
    const shown = rev && !s.folded && (!hand || hand.street === "showdown") ? rev : null;
    node.append(...[
      el("div", { class: "pk-seat-top" }, avatar(s.avatar_seed ?? s.user_id),
        el("span", { class: "pk-name" }, mine ? t("poker.you") : s.display_name),
        s.is_dealer || hand?.dealer_seat === s.seat ? el("span", { class: "pk-badge pk-badge--d", title: t("poker.dealer") }, "D") : null),
      el("div", { class: "pk-stack" }, chips(s.stack, { max: 1 })),
      (inHand || shown) && !mine ? el("div", { class: "pk-seatcards" }, ...(shown && shown.length ? shown.map((c) => cardEl(c, { size: "xs" })) : [cardEl(null, { size: "xs" }), cardEl(null, { size: "xs" })])) : null,
      s.all_in ? el("span", { class: "pk-tag pk-tag--allin" }, t("poker.allin")) : null,
      s.status === "away" ? el("span", { class: "pk-tag" }, t("poker.away")) : s.status === "sitting_out" ? el("span", { class: "pk-tag" }, t("poker.sitting_out")) : null,
      turn ? el("span", { class: "pk-timer", role: "presentation" }, el("i", { class: "pk-timer-fill" })) : null].filter(Boolean));
    node.setAttribute("aria-label", `${s.display_name}: ${fmt(s.stack)}${s.folded ? `, ${t("poker.folded")}` : ""}${turn ? `, ${t("poker.turn_of")}` : ""}`);
    // aposta atual à frente do lugar (em direção ao centro)
    if (s.bet > 0) {
      const b = el("div", { class: "pk-bet", "data-bet": String(s.seat) }, chips(s.bet, { max: 3 }));
      b.style.left = `${50 + (pos.x - 50) * 0.56}%`; b.style.top = `${50 + (pos.y - 50) * 0.56}%`;
      seatsLayer.append(b);
    }
    return node;
  }

  // ---------- render principal ----------
  function update() {
    const snap = live.snap();
    if (!snap) return;
    const hand = snap.hand;
    const n = snap.table?.max_seats || snap.seats?.length || 6;
    if (hand?.id !== lastHandId) { lastHandId = hand?.id ?? null; shownBoard = 0; }
    seatsLayer.replaceChildren();
    const seats = Array.from({ length: n }, (_, i) => snap.seats?.find((s) => s.seat === i) || { seat: i, user_id: null });
    const nodes = seats.map((s, i) => seatNode({ ...s, seat: s.seat ?? i }, i, n, snap));
    seatsLayer.prepend(...nodes);

    // mesa: cartas comunitárias, pote e side pots
    const bd = (hand?.board || snap.last_hand?.board || []).map(normCard).filter(Boolean);
    board.replaceChildren(...Array.from({ length: 5 }, (_, i) => (bd[i] ? cardEl(bd[i], { size: "md" }) : cardSlot("md"))));
    const pots = hand?.pots || [];
    const total = hand?.pot ?? pots.reduce((a, p) => a + p.amount, 0);
    if (hand?.street === "showdown" && !hand.board) shownBoard = 5;
    potEl.replaceChildren(total > 0 ? chips(total, { max: 5 }) : el("span", { class: "pk-pot-empty" }, t("poker.pot_empty")),
      el("small", { class: "pk-potlabel" }, `${t("poker.pot")}: ${fmt(total)}`),
      ...(pots.length > 1 ? [el("ul", { class: "pk-sidepots" }, ...pots.map((p, i) => el("li", {}, `${i === 0 ? t("poker.main_pot") : t("poker.side_pot", { n: i })}: ${fmt(p.amount)}`)))] : []));

    // as minhas cartas (só as minhas; vêm do snapshot privado)
    const hole = (snap.me?.hole || []).map(normCard).filter(Boolean);
    const myS = snap.seats?.find((s) => s.user_id === snap.me?.user_id);
    meCards.replaceChildren(...(hole.length ? hole.map((c) => cardEl(c, { size: "xl" })) : []));
    meCards.classList.toggle("is-folded", !!myS?.folded);
    meInfo.textContent = !snap.me?.seat && snap.me?.seat !== 0 ? t("poker.watching") : hole.length ? (myS?.folded ? t("poker.folded") : "") : hand ? "" : (snap.seats || []).filter((x) => x.user_id).length < 2 ? t("poker.waiting_players") : "";
    renderBar(snap);
    tickTimer();
    // animações pendentes (os nós acabaram de ser recriados)
    requestAnimationFrame(() => { while (afterRender.length) afterRender.shift()(); });
    shownBoard = bd.length;
  }

  // ---------- barra de ações ----------
  function renderBar(snap) {
    const hand = snap.hand, me = snap.me || {};
    const mine = me.seat != null && hand?.to_act === me.seat && hand.street !== "showdown";
    const myS = snap.seats?.find((s) => s.user_id === me.user_id);
    if (myS && (myS.status === "away" || myS.status === "sitting_out")) {
      bar.hidden = false;
      bar.replaceChildren(el("p", { class: "pk-hint" }, t("poker.you_are_away")), el("button", { type: "button", class: "btn-pixel btn-pixel--accent btn-pixel--lg", onclick: async () => { try { await live.back(); } catch (err) { toast(errorText(err), "error"); } } }, t("poker.back_to_table")));
      bar.classList.remove("is-mine");
      return;
    }
    if (me.seat == null || !myS) { bar.replaceChildren(me.seat == null ? el("p", { class: "pk-hint" }, t("poker.pick_seat")) : null); bar.hidden = me.seat != null; return; }
    bar.hidden = false;
    const stack = myS.stack || 0;
    const toCall = Math.max(0, me.to_call ?? Math.max(0, (hand?.current_bet ?? 0) - (myS.bet ?? 0)));
    const canCheck = me.can_check ?? toCall === 0;
    const maxTo = me.max_raise_to ?? (myS.bet ?? 0) + stack;
    const minTo = Math.min(maxTo, me.min_raise_to ?? ((hand?.current_bet ?? 0) + (hand?.min_raise ?? snap.table?.big_blind ?? 2)));
    const potNow = hand?.pot ?? 0;
    if (raiseTo == null || raiseTo < minTo || raiseTo > maxTo) raiseTo = minTo;
    const canRaise = maxTo > (hand?.current_bet ?? 0) && stack > toCall;
    const isBet = (hand?.current_bet ?? 0) === 0;
    const off = !mine || busy;

    const mk = (cls, label, onclick, disabled = off) => el("button", { type: "button", class: `btn-pixel pk-btn ${cls}`, disabled, onclick }, label);
    const callAll = !canCheck && toCall >= stack;
    const slider = el("input", { type: "range", class: "pk-slider", min: String(minTo), max: String(maxTo), step: "1", value: String(raiseTo), "aria-label": t("poker.raise_amount"), disabled: off || !canRaise });
    const amountOut = el("output", { class: "pk-raise-out" }, fmt(raiseTo));
    const setTo = (v) => { raiseTo = Math.max(minTo, Math.min(maxTo, Math.round(v))); slider.value = String(raiseTo); amountOut.textContent = fmt(raiseTo); raiseBtn.textContent = raiseLabel(); };
    const raiseLabel = () => (raiseTo >= maxTo ? t("poker.allin_n", { n: fmt(maxTo) }) : isBet ? t("poker.bet_n", { n: fmt(raiseTo) }) : t("poker.raise_n", { n: fmt(raiseTo) }));
    const raiseBtn = mk("btn-pixel--accent", raiseLabel(), () => send(raiseTo >= maxTo ? ACTION.allIn : isBet ? ACTION.bet : ACTION.raise, raiseTo), off || !canRaise);
    slider.addEventListener("input", () => setTo(Number(slider.value)));
    const quick = (label, v) => el("button", { type: "button", class: "btn-pixel btn-pixel--ghost pk-quick", disabled: off || !canRaise, onclick: () => setTo(v) }, label);
    const callBtn = mk("", canCheck ? t("poker.check") : callAll ? t("poker.allin_n", { n: fmt(stack) }) : t("poker.call_n", { n: fmt(Math.min(toCall, stack)) }),
      () => send(canCheck ? ACTION.check : callAll ? ACTION.allIn : ACTION.call, canCheck ? undefined : callAll ? undefined : undefined));
    bar.replaceChildren(
      el("div", { class: "pk-quickrow" }, quick("½ " + t("poker.pot_short"), (hand?.current_bet ?? 0) + potNow / 2), quick(t("poker.pot_short"), (hand?.current_bet ?? 0) + potNow), quick(t("poker.allin"), maxTo), amountOut, slider),
      el("div", { class: "pk-btnrow" }, mk("btn-pixel--danger", t("poker.fold"), () => send(ACTION.fold)), callBtn, raiseBtn));
    bar.classList.toggle("is-mine", mine);
  }

  async function send(type, amount) {
    if (busy) return;
    busy = true; renderBar(live.snap());
    try { await live.act(type, amount); say(t(`poker.said_${type}`)); }
    catch (err) { toast(errorText(err), "error"); }
    busy = false; renderBar(live.snap());
  }

  // atalhos de teclado: F = fold, C = check/call, R = apostar/subir (só se for a minha vez e não estiver a escrever)
  const onKey = (ev) => {
    if (ev.target.closest?.("input, textarea, select") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const btns = bar.querySelectorAll(".pk-btnrow button");
    const idx = { f: 0, c: 1, r: 2 }[ev.key.toLowerCase()];
    if (idx != null && btns[idx] && !btns[idx].disabled) { ev.preventDefault(); btns[idx].click(); }
  };
  document.addEventListener("keydown", onKey);

  // ---------- temporizador da vez (prazo do servidor, relógio corrigido) ----------
  function tickTimer() {
    const snap = live.snap();
    const hand = snap?.hand;
    const sec = remaining();
    const turnSeat = hand?.to_act;
    const fill = seatsLayer.querySelector(".is-turn .pk-timer-fill");
    if (sec != null && turnSeat != null && hand.street !== "showdown") {
      const who = snap.seats?.find((s) => s.seat === turnSeat);
      const mineTurn = who?.user_id === snap.me?.user_id;
      timerBanner.textContent = mineTurn ? t("poker.your_turn", { s: Math.ceil(sec) }) : t("poker.turn_of_n", { name: who?.display_name ?? "?", s: Math.ceil(sec) });
      timerBanner.classList.toggle("is-danger", sec <= 8);
      timerBanner.classList.toggle("is-mine", mineTurn);
      if (fill) { fill.style.width = `${Math.round((sec / TURN_SECONDS) * 100)}%`; fill.classList.toggle("is-danger", sec <= 8); }
    } else {
      const nh = snap?.table?.next_hand_at ? Date.parse(snap.table.next_hand_at) - (Date.now() + live.offset()) : null;
      timerBanner.textContent = hand ? "" : nh != null && nh > 0 ? t("poker.next_hand_in", { s: Math.ceil(nh / 1000) }) : t("poker.between_hands");
      timerBanner.classList.remove("is-danger", "is-mine");
    }
  }
  const iv = setInterval(tickTimer, 250);

  // ---------- eventos: registo e animações ----------
  const T = (key, vars) => t(`poker.log_${key}`, vars);
  async function onEvent(ev) {
    const p = ev.payload || {};
    const snap = live.snap();
    const who = p.display_name || nameOf(p.user_id);
    if (ev.type === "hand_started") pushLog(T("hand", { n: p.hand_number ?? p.hand_id ?? "" }));
    else if (ev.type === "action") {
      const type = p.type;
      pushLog(type === "fold" ? T("fold", { name: who }) : type === "check" ? T("check", { name: who }) : type === "call" ? T("call", { name: who, n: fmt(p.amount) }) : type === "all_in" || type === "allin" ? T("allin", { name: who, n: fmt(p.amount) }) : T(type === "bet" ? "bet" : "raise", { name: who, n: fmt(p.amount) }));
      if (p.amount > 0) flyChips(`[data-seat="${p.seat}"]`, ".pk-pot");
    } else if (ev.type === "street") pushLog(T("street", { street: t(`poker.street_${p.street}`) }));
    else if (ev.type === "showdown") pushLog(T("showdown"));
    else if (ev.type === "pot_awarded") {
      for (const a of p.awards || p.winners || []) { pushLog(T("won", { name: nameOf(a.user_id), n: fmt(a.amount) })); flyChips(".pk-pot", `[data-seat="${a.seat ?? snap?.seats?.find((s) => s.user_id === a.user_id)?.seat}"]`); }
    } else if (ev.type === "hand_ended") handEndToast(p);
    animateEvent(ev);
  }

  // Toast "+12 pts" / "−8 pts" no fim da mão: o servidor manda o líquido de cada jogador em hand_ended.nets (o mesmo que grava em poker_net)
  function handEndToast(p) {
    const uid = live.snap()?.me?.user_id;
    const net = Math.round((p.nets || {})[uid] ?? NaN);
    if (!Number.isFinite(net) || toastedHand === p.hand_id) return;
    toastedHand = p.hand_id;
    if (net !== 0) toast(t(net > 0 ? "poker.net_win" : "poker.net_loss", { n: fmt(Math.abs(net)) }), net > 0 ? "success" : "error");
  }

  async function animateEvent(ev) {
    if (reducedMotion()) return;
    const m = await motion();
    if (!m) return;
    const { gsap } = m;
    if (ev.type === "hand_started") afterRender.push(() => gsap.from([...meCards.children, ...seatsLayer.querySelectorAll(".pk-seatcards .pk-card")], { y: -30, opacity: 0, scale: 0.6, ease: "steps(5)", duration: 0.4, stagger: 0.07 }));
    if (ev.type === "street") afterRender.push(() => { const kids = [...board.children].slice(shownBoard); gsap.from(kids.filter((k) => !k.classList.contains("pk-card--slot")), { y: -26, opacity: 0, scale: 0.6, ease: "steps(5)", duration: 0.4, stagger: 0.12 }); });
    if (ev.type === "showdown") afterRender.push(() => gsap.from(seatsLayer.querySelectorAll(".pk-seatcards .pk-card:not(.pk-card--back)"), { scale: 0.4, opacity: 0, ease: "steps(4)", duration: 0.35, stagger: 0.05 }));
  }

  // fichas que voam de um sítio para outro (camada .pk-fly; só com movimento permitido)
  async function flyChips(fromSel, toSel) {
    if (reducedMotion()) return;
    const m = await motion();
    const a = tableEl.querySelector(fromSel), b = tableEl.querySelector(toSel);
    if (!m || !a || !b) return;
    const r = tableEl.getBoundingClientRect(), ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const chip = chipImg("pk-chip--c3"); chip.classList.add("pk-chip--fly");
    fly.append(chip);
    m.gsap.fromTo(chip, { x: ra.left - r.left + ra.width / 2, y: ra.top - r.top + ra.height / 2, opacity: 1, scale: 1.1 },
      { x: rb.left - r.left + rb.width / 2, y: rb.top - r.top + rb.height / 2, opacity: 0.2, scale: 0.8, duration: 0.55, ease: "steps(8)", onComplete: () => chip.remove() });
  }

  return {
    update, onEvent,
    destroy() { clearInterval(iv); document.removeEventListener("keydown", onKey); host.replaceChildren(); },
  };
}

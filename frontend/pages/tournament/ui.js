// Pequenos auxiliares partilhados pelo ecrã do aluno e pelo projetor (cores de agência, nomes, posição própria).
import { pick } from "../challenge/lib.js";
import { t } from "../../services/i18n.js";

// Classes literais para o Tailwind as encontrar (cores team-0..7 vêm do design)
export const TEAM_BG = ["bg-team-0", "bg-team-1", "bg-team-2", "bg-team-3", "bg-team-4", "bg-team-5", "bg-team-6", "bg-team-7"];
export const TEAM_TEXT = ["text-team-0", "text-team-1", "text-team-2", "text-team-3", "text-team-4", "text-team-5", "text-team-6", "text-team-7"];

export const roundTitle = (r) => (r ? pick(r.title) || t("tournament.round_n", { n: r.idx }) : "");
export const currentRound = (snap) => snap.rounds?.find((r) => r.idx === snap.tournament.current_round) || null;
export const nextRound = (snap) => snap.rounds?.find((r) => r.state === "pending" && (snap.tournament.current_round == null || r.idx > snap.tournament.current_round)) || null;

// Linha do próprio aluno (ou da sua agência) no ranking
export function myRow(snap) {
  const m = snap.me || {};
  return snap.leaderboard?.find((r) => r.participant_key === m.participant_key) || null;
}
export const myTeam = (snap) => snap.teams?.find((x) => x.id === snap.me?.team_id) || null;
export const mode = (snap) => snap.tournament.mode;

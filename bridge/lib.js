// Lógica pura da ponte (sem dependência do Baileys, para poder ser testada isoladamente).
import fs from 'node:fs';
import path from 'node:path';

export const EXIT = { OK: 0, CONFIG: 2, NEEDS_INPUT: 3, STOPPED: 4 };

// ---------------------------------------------------------------- .env
export function parseEnvText(text) {
  const out = {};
  for (let line of String(text).split(/\r?\n/)) {
    line = line.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    if (line.startsWith('export ')) line = line.slice(7).trimStart();
    const i = line.indexOf('=');
    const key = line.slice(0, i).trim();
    let value = line.slice(i + 1).trim();
    if (value.length >= 2 && value[0] === value.at(-1) && (value[0] === '"' || value[0] === "'")) {
      value = value.slice(1, -1);
    }
    if (key) out[key] = value;
  }
  return out;
}

/** Carrega o .env sem sobrescrever variáveis já definidas no ambiente. */
export function loadEnv(file, env = process.env) {
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch {
    return false;
  }
  for (const [k, v] of Object.entries(parseEnvText(text))) {
    if (env[k] === undefined) env[k] = v;
  }
  return true;
}

// ---------------------------------------------------------------- telefone / pareamento
/** Aceita "+55 (11) 99999-9999", "11999999999", "5511999999999"... Sem DDI (10-11 dígitos) assume Brasil. */
export function normalizePhone(input) {
  let d = String(input ?? '').replace(/\D/g, '').replace(/^0+/, '');
  if (d.length < 10) return { ok: false, error: 'Número curto demais. Informe DDI + DDD + número, ex.: 5511999999999.' };
  if (d.length > 15) return { ok: false, error: 'Número longo demais (máximo de 15 dígitos, incluindo o DDI).' };
  let assumedBrazil = false;
  if (d.length <= 11) {
    d = '55' + d;
    assumedBrazil = true;
  }
  return { ok: true, phone: d, assumedBrazil };
}

export function formatPhoneDisplay(phone) {
  const m = /^55(\d{2})(9?\d{4})(\d{4})$/.exec(phone);
  return m ? `+55 ${m[1]} ${m[2]}-${m[3]}` : `+${phone}`;
}

export function maskPhone(phone) {
  const p = String(phone);
  return p.length > 6 ? p.slice(0, 4) + '*'.repeat(p.length - 6) + p.slice(-2) : '***';
}

export function formatPairingCode(code) {
  const c = String(code ?? '').replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  return c.length === 8 ? `${c.slice(0, 4)}-${c.slice(4)}` : c;
}

// ---------------------------------------------------------------- desconexões
/** Decide o que fazer conforme o código de desconexão do WhatsApp (valores de DisconnectReason do Baileys). */
export function classifyDisconnect(code) {
  switch (code) {
    case 401: // loggedOut
      return { action: 'reauth', reason: 'A sessão foi encerrada pelo WhatsApp (aparelho removido).' };
    case 500: // badSession
      return { action: 'reauth', reason: 'A sessão salva está corrompida ou inválida.' };
    case 411: // multideviceMismatch
      return { action: 'reauth', reason: 'A sessão salva é incompatível (multi-dispositivo).' };
    case 440: // connectionReplaced
      return { action: 'replaced', reason: 'Outra conexão foi aberta com esta mesma sessão (conexão substituída).' };
    case 403: // forbidden
      return { action: 'stop', reason: 'O WhatsApp recusou a conexão (conta restrita ou bloqueada?).' };
    case 515: // restartRequired
      return { action: 'restart', reason: 'Reinício necessário (normal logo após o pareamento).' };
    default:
      return { action: 'reconnect', reason: `Conexão perdida (código ${code ?? 'desconhecido'}).` };
  }
}

export function backoffMs(attempt) {
  return Math.min(60_000, 2_000 * 2 ** Math.max(0, attempt));
}

/** Limita quantas vezes pedimos nova autenticação (evita loop que o WhatsApp possa interpretar como abuso). */
export class ReauthLimiter {
  constructor(max = 3, windowMs = 3_600_000, now = Date.now) {
    this.max = max;
    this.windowMs = windowMs;
    this.now = now;
    this.hits = [];
  }

  allow() {
    const t = this.now();
    this.hits = this.hits.filter((h) => t - h < this.windowMs);
    if (this.hits.length >= this.max) return false;
    this.hits.push(t);
    return true;
  }
}

// ---------------------------------------------------------------- sessão em disco
/** Há uma sessão salva e registrada (já pareada)? */
export function hasSession(authDir) {
  try {
    const creds = JSON.parse(fs.readFileSync(path.join(authDir, 'creds.json'), 'utf8'));
    return creds?.registered === true;
  } catch {
    return false;
  }
}

/** Apaga as credenciais (inválidas) e recria a pasta vazia com permissão restrita. */
export function wipeAuth(authDir) {
  fs.rmSync(authDir, { recursive: true, force: true });
  fs.mkdirSync(authDir, { recursive: true, mode: 0o700 });
}

// ---------------------------------------------------------------- compatibilidade de módulo
export function pick(mod, name) {
  return mod?.[name] ?? mod?.default?.[name];
}

export function resolveMakeSocket(mod) {
  return [mod?.default, mod?.default?.default, mod?.makeWASocket, mod?.default?.makeWASocket].find(
    (c) => typeof c === 'function',
  );
}

// ---------------------------------------------------------------- identificadores
export function normalizeJid(jid) {
  return typeof jid === 'string' ? jid.replace(/:\d+@/, '@') : '';
}

/** Mapeia ids alternativos (lid / telefone) de cada participante para o JID de telefone, quando disponível. */
export function buildIdentityMap(participants = []) {
  const map = new Map();
  for (const p of participants) {
    const phone = normalizeJid(p.phoneNumber || (String(p.id ?? '').endsWith('@s.whatsapp.net') ? p.id : ''));
    if (!phone) continue;
    for (const alt of [p.id, p.lid, p.phoneNumber]) {
      if (alt) map.set(normalizeJid(alt), phone);
    }
  }
  return map;
}

export function canonicalJid(jid, map) {
  const n = normalizeJid(jid);
  return map?.get(n) ?? n;
}

// ---------------------------------------------------------------- mensagens recebidas
export function unwrap(message) {
  let m = message;
  for (let i = 0; i < 5 && m; i++) {
    const inner =
      m.ephemeralMessage?.message ??
      m.viewOnceMessage?.message ??
      m.viewOnceMessageV2?.message ??
      m.documentWithCaptionMessage?.message;
    if (!inner) break;
    m = inner;
  }
  return m ?? {};
}

export function extractText(m) {
  return m.conversation ?? m.extendedTextMessage?.text ?? m.imageMessage?.caption ?? m.videoMessage?.caption ?? '';
}

function lenToNumber(v) {
  if (v && typeof v === 'object' && typeof v.toNumber === 'function') return v.toNumber();
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

/** Áudio/imagem anexados (só metadados; o download é feito depois, se o bot pedir). */
export function mediaHint(inner) {
  const a = inner?.audioMessage;
  if (a) return { kind: 'audio', mime: a.mimetype || 'audio/ogg', seconds: lenToNumber(a.seconds), size: lenToNumber(a.fileLength) };
  const i = inner?.imageMessage;
  if (i) return { kind: 'image', mime: i.mimetype || 'image/jpeg', seconds: 0, size: lenToNumber(i.fileLength) };
  return null;
}

export const MEDIA_LIMITS = { audio: { bytes: 4_000_000, seconds: 180 }, image: { bytes: 5_000_000, seconds: 0 } };
export function mediaAllowed(hint) {
  const lim = MEDIA_LIMITS[hint?.kind];
  if (!lim) return false;
  if (hint.size > lim.bytes) return false;
  return !(lim.seconds && hint.seconds > lim.seconds);
}

function tsToNumber(ts) {
  if (ts && typeof ts === 'object' && typeof ts.toNumber === 'function') return ts.toNumber();
  const n = Number(ts);
  return Number.isFinite(n) && n > 0 ? n : Math.floor(Date.now() / 1000);
}

/** Converte uma mensagem do Baileys no formato do gateway Python (ou null se não deve ser processada). */
const sentIds = new Set();
/** Guarda o id de mensagens enviadas pelo próprio bot, para nunca tratá-las como comandos (evita laço). */
const sentContent = new Map();
export function rememberSent(id, message) {
  if (!id) return;
  sentIds.add(id);
  if (sentIds.size > 500) sentIds.delete(sentIds.values().next().value);
  // Guarda o conteúdo para o WhatsApp poder pedir reenvio ("Aguardando mensagem"): o Baileys chama getMessage.
  if (message) {
    sentContent.set(id, message);
    if (sentContent.size > 300) sentContent.delete(sentContent.keys().next().value);
  }
}

/** Conteúdo de uma mensagem que o bot enviou (para reenvio quando o aparelho não conseguiu decifrar). */
export function getSent(id) {
  return sentContent.get(id);
}

export function parseIncoming(m, botId = '') {
  if (!m?.message) return null;
  const chat = m.key?.remoteJid ?? '';
  if (chat === 'status@broadcast') return null;
  const isGroup = chat.endsWith('@g.us');
  const fromMe = Boolean(m.key?.fromMe);
  // Mensagens da própria conta (bot rodando no número do dono) seguem para o Python com from_me=true: lá valem só como
  // comando (grupos e conversa consigo mesmo) ou como sinal de que o dono assumiu uma conversa direta.
  if (fromMe && sentIds.has(m.key?.id)) return null;
  if (!isGroup && !chat.endsWith('@s.whatsapp.net') && !chat.endsWith('@lid')) return null;
  const inner = unwrap(m.message);
  const text = extractText(inner).trim();
  const hint = mediaHint(inner);
  if (!text && !hint) return null;
  const sender = fromMe ? botId : isGroup ? m.key.participant : chat;
  if (!sender) return null;
  const ctx = inner.extendedTextMessage?.contextInfo ?? {};
  return {
    chat_id: chat,
    sender,
    text,
    is_group: isGroup,
    sender_name: m.pushName ?? '',
    bot_id: botId,
    mentioned: ctx.mentionedJid ?? [],
    quoted_sender: ctx.participant ?? null,
    message_id: m.key.id,
    timestamp: tsToNumber(m.messageTimestamp),
    from_me: fromMe,
    ...(hint ? { media_hint: hint } : {}),
  };
}

// ---------------------------------------------------------------- envio
/** Fila de envio: uma tarefa por vez, com intervalo mínimo (reduz risco de bloqueio por excesso de mensagens). */
export function createSender(gapMs = 700, onError = () => {}, sleep = (ms) => new Promise((r) => setTimeout(r, ms))) {
  let chain = Promise.resolve();
  return function enqueue(task) {
    chain = chain.then(async () => {
      try {
        await task();
      } catch (err) {
        onError(err);
      }
      await sleep(gapMs);
    });
    return chain;
  };
}

const ALLOWED_ACTIONS = new Set(['delete', 'kick', 'set_description', 'set_subject', 'set_announce']);
const isGroupJid = (j) => typeof j === 'string' && j.endsWith('@g.us');
const isUserJid = (j) => typeof j === 'string' && /@(s\.whatsapp\.net|lid)$/.test(j);

/** Envia a resposta e executa apenas ações permitidas, restritas ao próprio chat da resposta. */
const CONTROL_ACTIONS = new Set(['shutdown', 'logout']);

export async function perform(sock, enqueue, chatJid, reply, original, control = {}) {
  if (reply.text || reply.image_base64 || reply.audio_base64) {
    const mentions = Array.isArray(reply.mentions) ? reply.mentions.filter(isUserJid) : [];
    let content;
    if (reply.audio_base64) {
      const mimetype = typeof reply.audio_mimetype === 'string' && /^audio\/[\w.+-]+(;[\w=\s.-]+)?$/.test(reply.audio_mimetype)
        ? reply.audio_mimetype : 'audio/ogg; codecs=opus';
      content = { audio: Buffer.from(reply.audio_base64, 'base64'), mimetype, ptt: Boolean(reply.ptt) };
    } else if (reply.image_base64) {
      content = { image: Buffer.from(reply.image_base64, 'base64'), caption: reply.text || undefined, mentions };
    } else {
      content = { text: String(reply.text).slice(0, 8000), mentions };
    }
    await enqueue(async () => {
      const sent = await sock.sendMessage(chatJid, content, reply.quote && original ? { quoted: original } : {});
      rememberSent(sent?.key?.id, sent?.message);
    });
  }
  for (const action of reply.actions ?? []) {
    if (CONTROL_ACTIONS.has(action?.type)) {
      // controle da própria ponte (só o dono consegue gerar isso, via comando); espera a resposta sair antes
      await enqueue(async () => {});
      if (typeof control[action.type] === 'function') await control[action.type]();
      continue;
    }
    if (!ALLOWED_ACTIONS.has(action?.type) || !isGroupJid(action.chat_id) || action.chat_id !== chatJid) continue;
    if (action.type === 'delete') {
      if (typeof action.message_id !== 'string' || !isUserJid(action.participant)) continue;
      await enqueue(() =>
        sock.sendMessage(action.chat_id, {
          delete: { remoteJid: action.chat_id, fromMe: false, id: action.message_id, participant: action.participant },
        }),
      );
    } else if (action.type === 'kick') {
      const users = (Array.isArray(action.users) ? action.users : []).filter(isUserJid).slice(0, 5);
      if (users.length) await enqueue(() => sock.groupParticipantsUpdate(action.chat_id, users, 'remove'));
    } else if (action.type === 'set_description') {
      if (typeof action.text === 'string') {
        await enqueue(() => sock.groupUpdateDescription(action.chat_id, action.text.slice(0, 512)));
      }
    } else if (action.type === 'set_subject') {
      const name = typeof action.text === 'string' ? action.text.trim().slice(0, 100) : '';
      if (name) await enqueue(() => sock.groupUpdateSubject(action.chat_id, name));
    } else if (action.type === 'set_announce') {
      // true = só administradores enviam mensagens; false = todos
      if (typeof action.announce === 'boolean') {
        await enqueue(() => sock.groupSettingUpdate(action.chat_id, action.announce ? 'announcement' : 'not_announcement'));
      }
    }
  }
}

// Ponte WhatsApp (Baileys) <-> gateway Python do Robô Nicolas 🤖.
// ATENÇÃO: o Baileys é uma biblioteca NÃO oficial do WhatsApp. Use, de preferência, um número dedicado
// ao bot e respeite os Termos de Serviço do WhatsApp (há risco de restrição/banimento da conta).
import path from 'node:path';
import readline from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import * as lib from './lib.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
lib.loadEnv(path.join(ROOT, '.env'));

const env = process.env;
const TOKEN = env.BRIDGE_TOKEN ?? '';
const HOST = env.HOST && env.HOST !== '0.0.0.0' ? env.HOST : '127.0.0.1';
const BOT_URL = env.BOT_URL || `http://${HOST}:${env.PORT || 8787}`;
const AUTH_DIR = path.resolve(ROOT, env.AUTH_DIR || 'auth');
const SEND_GAP_MS = Number(env.SEND_GAP_MS ?? 700);
// A biblioteca do WhatsApp é muito falante (timeouts de rede viram blocos enormes de JSON). Só mostramos com LOG_LEVEL=debug.
const LOG_LEVEL = (env.LOG_LEVEL || '').toLowerCase() === 'debug' ? 'debug' : 'silent';
const INTERACTIVE = Boolean(process.stdin.isTTY && process.stdout.isTTY);

const stamp = () => new Date().toLocaleTimeString('pt-BR');
const info = (...a) => console.log(`[${stamp()}]`, ...a);
const warn = (...a) => console.warn(`[${stamp()}]`, ...a);

function fatal(code, message) {
  (code === lib.EXIT.OK ? console.log : console.error)(`\n${message}\n`);
  process.exit(code);
}

if (!TOKEN || TOKEN.length < 16) {
  fatal(lib.EXIT.CONFIG, 'BRIDGE_TOKEN ausente ou curto demais no .env. Rode: bash install.sh (ele gera o token).');
}

// ------------------------------------------------------------------ dependências
let baileys;
try {
  baileys = await import('@whiskeysockets/baileys');
} catch (err) {
  fatal(lib.EXIT.CONFIG, `Dependências do WhatsApp não instaladas (${err.code ?? err.message}).\nRode: bash install.sh`);
}
const makeWASocket = lib.resolveMakeSocket(baileys);
const useMultiFileAuthState = lib.pick(baileys, 'useMultiFileAuthState');
const fetchLatestBaileysVersion = lib.pick(baileys, 'fetchLatestBaileysVersion');
const Browsers = lib.pick(baileys, 'Browsers');
const downloadMediaMessage = lib.pick(baileys, 'downloadMediaMessage');
if (!makeWASocket || !useMultiFileAuthState) {
  fatal(lib.EXIT.CONFIG, 'A versão instalada do Baileys não expõe a API esperada. Veja o README (seção Versões).');
}
let qrTerminal = null;
try {
  qrTerminal = (await import('qrcode-terminal')).default;
} catch {
  /* só necessário para o modo QR */
}
const { default: pino } = await import('pino');
const logger = pino({ level: LOG_LEVEL });

// ------------------------------------------------------------------ estado
const state = {
  gen: 0, // identifica o socket atual; eventos de sockets antigos são ignorados
  auth: null, // { method: 'code'|'qr', phone } enquanto ainda não pareado
  retries: 0,
  pollTimer: null,
  sock: null,
  pairFailures: 0,
  codeShown: false,
  groupCache: new Map(),
  lastGatewayError: 0,
};
const reauth = new lib.ReauthLimiter(3, 3_600_000);
const enqueue = lib.createSender(SEND_GAP_MS, (e) => warn('falha no envio:', e?.message ?? e));

// ------------------------------------------------------------------ autenticação (escolha do método)
async function chooseAuth() {
  let method = (env.AUTH_METHOD || '').trim().toLowerCase();
  if (method !== 'code' && method !== 'qr') method = '';
  let phoneRaw = env.PAIRING_PHONE || '';
  const fromEnv = Boolean(phoneRaw);

  if (!method && !INTERACTIVE) {
    fatal(
      lib.EXIT.NEEDS_INPUT,
      'É preciso autenticar no WhatsApp, mas não há terminal interativo.\n' +
        'Rode "bash start.sh" diretamente no Termux, ou defina AUTH_METHOD e PAIRING_PHONE no .env.',
    );
  }
  const rl = INTERACTIVE ? readline.createInterface({ input: process.stdin, output: process.stdout }) : null;
  try {
    if (!method) {
      console.log('\n=== Conectar ao WhatsApp ===');
      console.log(' 1) Código de pareamento (recomendado no celular: você digita um código no WhatsApp)');
      console.log(' 2) QR Code (precisa escanear com OUTRO aparelho)');
      for (;;) {
        const a = (await rl.question('Escolha [1]: ')).trim() || '1';
        if (a === '1') { method = 'code'; break; }
        if (a === '2') { method = 'qr'; break; }
        console.log('Digite 1 ou 2.');
      }
    }
    if (method === 'qr') return { method, phone: null };

    let phone = null;
    for (let tries = 0; tries < 5 && !phone; tries++) {
      if (!phoneRaw) {
        phoneRaw = await rl.question('Número do WhatsApp do bot, com DDI e DDD (ex.: 5511999999999): ');
      }
      const r = lib.normalizePhone(phoneRaw);
      if (!r.ok) {
        console.log(`⚠️  ${r.error}`);
        if (fromEnv) fatal(lib.EXIT.CONFIG, 'PAIRING_PHONE inválido no .env.');
        phoneRaw = '';
        continue;
      }
      if (!fromEnv) {
        if (r.assumedBrazil) console.log('ℹ️  Sem DDI informado: assumindo Brasil (+55).');
        const c = (await rl.question(`Usar ${lib.formatPhoneDisplay(r.phone)}? [S/n] `)).trim().toLowerCase();
        if (c && !['s', 'sim', 'y', 'yes'].includes(c)) { phoneRaw = ''; continue; }
      }
      phone = r.phone;
    }
    if (!phone) fatal(lib.EXIT.NEEDS_INPUT, 'Número inválido várias vezes. Rode "bash start.sh" para tentar de novo.');
    return { method, phone };
  } finally {
    rl?.close();
  }
}

function showPairingCode(code, phone) {
  const line = '═'.repeat(44);
  console.log(`\n${line}`);
  console.log(`  ${state.codeShown ? 'NOVO ' : ''}CÓDIGO DE PAREAMENTO:  ${lib.formatPairingCode(code)}`);
  console.log(line);
  console.log(`No WhatsApp do número ${lib.formatPhoneDisplay(phone)}:`);
  console.log('  1. Abra Configurações > Aparelhos conectados (Dispositivos conectados)');
  console.log('  2. Toque em "Conectar um aparelho"');
  console.log('  3. Escolha "Conectar com número de telefone" (opção abaixo do QR)');
  console.log('  4. Digite o código acima');
  console.log('O código expira em poucos minutos. Aguardando a confirmação do WhatsApp...\n');
  state.codeShown = true;
}

async function onChallenge(sock, qr, challenge) {
  if (state.auth?.method === 'qr') {
    console.log('\nEscaneie o QR Code abaixo com OUTRO aparelho:');
    console.log('WhatsApp > Configurações > Aparelhos conectados > Conectar um aparelho\n');
    if (qrTerminal) qrTerminal.generate(qr, { small: true });
    else warn('Módulo qrcode-terminal ausente; rode bash install.sh. Texto bruto do QR:', qr);
    return;
  }
  if (challenge.requested || !state.auth?.phone) return;
  challenge.requested = true;
  try {
    const code = await sock.requestPairingCode(state.auth.phone);
    state.pairFailures = 0;
    showPairingCode(code, state.auth.phone);
  } catch (err) {
    challenge.requested = false; // tenta de novo no próximo ciclo
    state.pairFailures += 1;
    warn(`Não foi possível gerar o código de pareamento (${err?.message ?? err}).`);
    if (state.pairFailures >= 3) {
      fatal(
        lib.EXIT.STOPPED,
        'Falhou 3 vezes ao gerar o código. Confira o número e a internet, ou use AUTH_METHOD=qr no .env.',
      );
    }
  }
}

// ------------------------------------------------------------------ gateway Python
async function callBot(pathname, payload) {
  const res = await fetch(BOT_URL + pathname, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Bridge-Token': TOKEN },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`gateway respondeu HTTP ${res.status}`);
  return res.json();
}

function gatewayDown(err) {
  if (Date.now() - state.lastGatewayError > 30_000) {
    state.lastGatewayError = Date.now();
    warn(`Gateway do bot indisponível (${err?.message ?? err}). Confira se o Python está rodando (logs/bot.log).`);
  }
}

async function groupMeta(sock, jid) {
  const hit = state.groupCache.get(jid);
  if (hit && Date.now() - hit.at < 60_000) return hit.meta;
  const meta = await sock.groupMetadata(jid);
  state.groupCache.set(jid, { at: Date.now(), meta });
  return meta;
}

// ------------------------------------------------------------------ mensagens
/** Baixa áudio/imagem só se o bot (modo esperto) pediu, e dentro dos limites de tamanho. */
async function attachMedia(sock, m, payload) {
  const hint = payload.media_hint;
  if (!hint || payload.from_me || typeof downloadMediaMessage !== 'function' || !lib.mediaAllowed(hint)) return;
  try {
    const ask = await callBot('/wants', { chat_id: payload.chat_id, is_group: payload.is_group });
    if (!ask.media) return;
    const buf = await downloadMediaMessage(m, 'buffer', {}, { logger, reuploadRequest: sock.updateMediaMessage });
    if (!buf?.length || buf.length > lib.MEDIA_LIMITS[hint.kind].bytes) return;
    payload.media = [{ kind: hint.kind, mime: hint.mime, seconds: hint.seconds, data: Buffer.from(buf).toString('base64') }];
  } catch (err) {
    warn(`Não consegui baixar o ${hint.kind === 'audio' ? 'áudio' : 'a imagem'} (${err?.message ?? err}).`);
  }
}

async function handleMessage(sock, m) {
  const botId = lib.normalizeJid(sock.user?.id ?? '');
  const payload = lib.parseIncoming(m, botId);
  if (!payload) return;
  await attachMedia(sock, m, payload);
  delete payload.media_hint;
  if (!payload.text && !payload.media?.length) return; // áudio/imagem que o bot não pediu: ignora
  if (payload.is_group) {
    const meta = await groupMeta(sock, payload.chat_id);
    const idmap = lib.buildIdentityMap(meta.participants);
    const adminIds = new Set();
    for (const p of meta.participants.filter((x) => x.admin)) {
      for (const id of [p.id, p.lid, p.phoneNumber]) if (id) adminIds.add(lib.normalizeJid(id));
    }
    const botIds = [botId, lib.normalizeJid(sock.user?.lid ?? '')].filter(Boolean);
    payload.sender = lib.canonicalJid(payload.sender, idmap);
    payload.mentioned = payload.mentioned.map((j) => lib.canonicalJid(j, idmap));
    payload.quoted_sender = payload.quoted_sender ? lib.canonicalJid(payload.quoted_sender, idmap) : null;
    payload.group_name = meta.subject;
    payload.group_size = meta.participants.length;
    payload.group_admins = [...new Set([...adminIds].map((j) => lib.canonicalJid(j, idmap)))];
    payload.sender_is_admin = payload.group_admins.includes(payload.sender);
    payload.bot_is_admin = botIds.some((b) => adminIds.has(b));
    payload.bot_id = botIds[0] ?? '';
  }
  let data;
  try {
    data = await callBot('/message', payload);
  } catch (err) {
    return gatewayDown(err);
  }
  for (const reply of data.replies ?? []) await lib.perform(sock, enqueue, payload.chat_id, reply, m, control);
}

async function handleParticipants(sock, update) {
  const type = update.action === 'add' ? 'join' : update.action === 'remove' ? 'leave' : null;
  if (!type) return;
  const meta = await groupMeta(sock, update.id).catch(() => null);
  const idmap = lib.buildIdentityMap(meta?.participants ?? []);
  const admins = meta ? meta.participants.filter((p) => p.admin).flatMap((p) => [p.id, p.lid, p.phoneNumber]).filter(Boolean) : [];
  const botIds = [lib.normalizeJid(sock.user?.id ?? ''), lib.normalizeJid(sock.user?.lid ?? '')].filter(Boolean);
  let data;
  try {
    data = await callBot('/event', {
      type,
      chat_id: update.id,
      users: update.participants.map((p) => lib.canonicalJid(typeof p === 'string' ? p : (p.phoneNumber || p.id), idmap)),
      group_name: meta?.subject ?? '',
      group_admins: [...new Set(admins.map((j) => lib.canonicalJid(j, idmap)))],
      bot_is_admin: admins.some((a) => botIds.includes(lib.normalizeJid(a))),
    });
  } catch (err) {
    return gatewayDown(err);
  }
  for (const reply of data.replies ?? []) await lib.perform(sock, enqueue, update.id, reply, null);
}

async function pollReminders(sock) {
  try {
    const res = await fetch(BOT_URL + '/due', { headers: { 'X-Bridge-Token': TOKEN }, signal: AbortSignal.timeout(10_000) });
    if (!res.ok) return;
    const { reminders } = await res.json();
    for (const item of reminders ?? []) await lib.perform(sock, enqueue, item.chat_id, item.reply, null);
  } catch (err) {
    gatewayDown(err);
  }
}

// ------------------------------------------------------------------ conexão
function onOpen(sock) {
  state.retries = 0;
  // só zera o contador de "conexão substituída" depois de 5 min estável (senão duas instâncias brigariam para sempre)
  clearTimeout(state.replacedReset);
  state.replacedReset = setTimeout(() => { state.replaced = 0; }, 300_000);
  state.auth = null;
  clearTimeout(state.connectTimer);
  startWatchdog(sock);
  state.pairFailures = 0;
  state.codeShown = false;
  const who = lib.maskPhone(String(sock.user?.id ?? '').split(/[:@]/)[0]);
  info(`✅ Autenticado e conectado ao WhatsApp (conta ${who}). O bot já responde aos comandos.`);
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(() => pollReminders(sock), 15_000);
}

/** Vigia a conexão: se o websocket morrer sem aviso, força a reconexão (24/7). */
function startWatchdog(sock) {
  clearInterval(state.watchdog);
  state.connected = true;
  let bad = 0;
  state.watchdog = setInterval(() => {
    if (state.sock !== sock) return clearInterval(state.watchdog);
    const ws = sock.ws;
    const open = typeof ws?.isOpen === 'boolean' ? ws.isOpen : typeof ws?.readyState === 'number' ? ws.readyState === 1 : true;
    bad = open ? 0 : bad + 1;
    if (bad >= 2) {
      warn('A conexão parece ter caído sem aviso. Reconectando...');
      bad = 0;
      try { sock.end(new Error('watchdog')); } catch { /* ignorado */ }
    }
  }, 30_000);
}

async function onClose(lastDisconnect) {
  state.connected = false;
  clearTimeout(state.replacedReset);
  clearInterval(state.watchdog);
  clearInterval(state.pollTimer);
  const code = lastDisconnect?.error?.output?.statusCode;
  const verdict = lib.classifyDisconnect(code);

  if (verdict.action === 'stop') fatal(lib.EXIT.STOPPED, `${verdict.reason}\nO bot foi encerrado para não disputar a sessão.`);

  if (verdict.action === 'replaced') {
    // Pode ser um processo antigo ainda vivo. Tenta de novo algumas vezes; se persistir, para para não brigar pela sessão.
    state.replaced = (state.replaced ?? 0) + 1;
    if (state.replaced > 3) {
      fatal(lib.EXIT.STOPPED, `${verdict.reason}\nHá outro bot usando esta sessão. Rode "bash stop.sh" e depois "bash start.sh".`);
    }
    warn(`${verdict.reason} Tentativa ${state.replaced}/3 em 20s... (se persistir, rode: bash stop.sh)`);
    return setTimeout(safeConnect, 20_000);
  }

  if (verdict.action === 'reauth') {
    warn(`⚠️  ${verdict.reason} Será preciso autenticar de novo.`);
    lib.wipeAuth(AUTH_DIR); // credenciais inválidas não servem mais: remove com segurança
    state.auth = null;
    if (!reauth.allow()) {
      fatal(lib.EXIT.STOPPED, 'A sessão foi invalidada várias vezes em pouco tempo. Aguarde um pouco e rode "bash start.sh" de novo.');
    }
    if (!INTERACTIVE && !env.AUTH_METHOD) {
      fatal(lib.EXIT.NEEDS_INPUT, 'Sessão removida. Rode "bash start.sh" no Termux para parear novamente.');
    }
    return setTimeout(safeConnect, 1000);
  }

  if (verdict.action === 'restart') {
    info(state.auth ? 'Pareamento aceito. Reiniciando a conexão para concluir...' : 'Reiniciando a conexão...');
    return setTimeout(safeConnect, 300);
  }

  const wait = lib.backoffMs(state.retries++);
  warn(`${verdict.reason} Reconectando em ${wait / 1000}s...`);
  setTimeout(safeConnect, wait);
}

async function connect() {
  const { state: authState, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  if (!authState.creds.registered) {
    if (!state.auth) state.auth = await chooseAuth();
  } else {
    state.auth = null;
  }
  let version;
  try {
    ({ version } = await fetchLatestBaileysVersion());
  } catch {
    /* usa a versão padrão da biblioteca */
  }
  const gen = ++state.gen;
  const sock = makeWASocket({
    ...(version ? { version } : {}),
    auth: authState,
    logger,
    printQRInTerminal: false,
    markOnlineOnConnect: false,
    syncFullHistory: false,
    keepAliveIntervalMs: 25_000,
    connectTimeoutMs: 60_000,
    defaultQueryTimeoutMs: 60_000,
    retryRequestDelayMs: 500,
    getMessage: async (key) => lib.getSent(key?.id), // reenvio quando o aparelho mostra "Aguardando mensagem"
    browser: Browsers?.ubuntu ? Browsers.ubuntu('Chrome') : ['Ubuntu', 'Chrome', '22.04.4'],
  });
  state.sock = sock;
  const challenge = { requested: false };
  // Se a conexão não abrir em 2 minutos (travada), derruba o socket para o ciclo de reconexão recomeçar.
  clearTimeout(state.connectTimer);
  state.connectTimer = setTimeout(() => {
    if (gen !== state.gen || state.connected) return;
    warn('A conexão com o WhatsApp não abriu em 2 minutos. Tentando de novo...');
    try { sock.end(new Error('connect-timeout')); } catch { /* ignorado */ }
  }, 120_000);

  sock.ev.on('creds.update', saveCreds); // grava a sessão em AUTH_DIR (persistência)
  sock.ev.on('connection.update', async (u) => {
    if (gen !== state.gen) return;
    try {
      if (u.qr && !authState.creds.registered && state.auth) await onChallenge(sock, u.qr, challenge);
      if (u.connection === 'open') onOpen(sock);
      if (u.connection === 'close') await onClose(u.lastDisconnect);
    } catch (err) {
      warn('erro ao tratar evento de conexão:', err?.message ?? err);
    }
  });
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (gen !== state.gen || type !== 'notify') return;
    for (const m of messages) {
      try {
        await handleMessage(sock, m);
      } catch (err) {
        warn('erro ao tratar mensagem:', err?.message ?? err);
      }
    }
  });
  sock.ev.on('group-participants.update', (u) => {
    if (gen !== state.gen) return;
    state.groupCache.delete(u.id);
    handleParticipants(sock, u).catch((err) => warn('erro em evento de grupo:', err?.message ?? err));
  });
  sock.ev.on('groups.update', (updates) => updates.forEach((u) => state.groupCache.delete(u.id)));
}

async function safeConnect() {
  try {
    await connect();
  } catch (err) {
    const wait = lib.backoffMs(state.retries++);
    warn(`Falha ao conectar (${err?.message ?? err}). Nova tentativa em ${wait / 1000}s...`);
    setTimeout(safeConnect, wait);
  }
}

// Controle pedido pelo dono via comando (.desligarbot / .desconectar)
const control = {
  async shutdown() {
    info('Desligamento pedido pelo dono. Encerrando (a sessão do WhatsApp foi preservada)...');
    clearInterval(state.pollTimer);
    try { state.sock?.end?.(undefined); } catch { /* ignorado */ }
    process.exit(lib.EXIT.OK);
  },
  async logout() {
    info('Desconexão pedida pelo dono. Saindo da conta do WhatsApp...');
    clearInterval(state.pollTimer);
    try { await state.sock?.logout?.(); } catch (err) { warn('Não consegui avisar o WhatsApp do logout:', err?.message ?? err); }
    lib.wipeAuth(AUTH_DIR);
    info('Sessão apagada. No próximo "bash start.sh" será preciso conectar de novo.');
    process.exit(lib.EXIT.OK);
  },
};

// Erros inesperados não derrubam o bot: registra e segue. Erro grave de verdade: sai e o start.sh reinicia.
process.on('unhandledRejection', (err) => warn('Erro não tratado (ignorado):', err?.message ?? err));
process.on('uncaughtException', (err) => {
  console.error('Erro inesperado na ponte:', err?.stack ?? err);
  process.exit(1); // código 1: o start.sh reinicia a ponte
});

// Encerramento limpo (Ctrl+C): NÃO faz logout, para preservar a sessão salva.
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    clearInterval(state.pollTimer);
    try {
      state.sock?.end?.(undefined);
    } catch {
      /* ignorado */
    }
    console.log('\nEncerrando a ponte (a sessão do WhatsApp foi preservada).');
    process.exit(lib.EXIT.OK);
  });
}

if (lib.hasSession(AUTH_DIR)) info('Sessão salva encontrada: conectando sem novo pareamento...');
else info('Nenhuma sessão salva: será necessário autenticar no WhatsApp.');
await safeConnect();

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import * as lib from '../lib.js';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'nicolas-'));

test('parseEnvText lida com emoji, aspas, comentários e export', () => {
  const env = lib.parseEnvText('# c\nBOT_NAME=Robô Nicolas 🤖\nA="x y"\nexport B=2\nVAZIO=\nlinha sem igual\n');
  assert.equal(env.BOT_NAME, 'Robô Nicolas 🤖');
  assert.equal(env.A, 'x y');
  assert.equal(env.B, '2');
  assert.equal(env.VAZIO, '');
  assert.equal(Object.keys(env).length, 4);
});

test('loadEnv não sobrescreve variáveis já definidas', () => {
  const dir = tmp();
  fs.writeFileSync(path.join(dir, '.env'), 'X=do_arquivo\nY=novo\n');
  const env = { X: 'do_ambiente' };
  assert.equal(lib.loadEnv(path.join(dir, '.env'), env), true);
  assert.equal(env.X, 'do_ambiente');
  assert.equal(env.Y, 'novo');
  assert.equal(lib.loadEnv(path.join(dir, 'nao-existe'), {}), false);
});

test('normalizePhone', () => {
  assert.deepEqual(lib.normalizePhone('+55 (11) 99999-9999'), { ok: true, phone: '5511999999999', assumedBrazil: false });
  assert.deepEqual(lib.normalizePhone('11999999999'), { ok: true, phone: '5511999999999', assumedBrazil: true });
  assert.equal(lib.normalizePhone('011 99999-9999').phone, '5511999999999');
  assert.equal(lib.normalizePhone('351912345678').phone, '351912345678');
  assert.equal(lib.normalizePhone('12345').ok, false);
  assert.equal(lib.normalizePhone('1'.repeat(16)).ok, false);
  assert.equal(lib.normalizePhone(undefined).ok, false);
});

test('formatação de telefone e código de pareamento', () => {
  assert.equal(lib.formatPhoneDisplay('5511999999999'), '+55 11 99999-9999');
  assert.equal(lib.formatPhoneDisplay('351912345678'), '+351912345678');
  assert.equal(lib.maskPhone('5511999999999'), '5511*******99');
  assert.equal(lib.formatPairingCode('abcd1234'), 'ABCD-1234');
  assert.equal(lib.formatPairingCode('ABCD-1234'), 'ABCD-1234');
  assert.equal(lib.formatPairingCode('XYZ'), 'XYZ');
});

test('classifyDisconnect', () => {
  assert.equal(lib.classifyDisconnect(401).action, 'reauth');
  assert.equal(lib.classifyDisconnect(500).action, 'reauth');
  assert.equal(lib.classifyDisconnect(411).action, 'reauth');
  assert.equal(lib.classifyDisconnect(440).action, 'replaced');
  assert.equal(lib.classifyDisconnect(403).action, 'stop');
  assert.equal(lib.classifyDisconnect(515).action, 'restart');
  assert.equal(lib.classifyDisconnect(408).action, 'reconnect');
  assert.equal(lib.classifyDisconnect(undefined).action, 'reconnect');
});

test('backoffMs cresce e é limitado', () => {
  assert.equal(lib.backoffMs(0), 2000);
  assert.equal(lib.backoffMs(1), 4000);
  assert.equal(lib.backoffMs(10), 60000);
  assert.equal(lib.backoffMs(-3), 2000);
});

test('ReauthLimiter bloqueia após o máximo e libera depois da janela', () => {
  let t = 0;
  const lim = new lib.ReauthLimiter(2, 1000, () => t);
  assert.equal(lim.allow(), true);
  assert.equal(lim.allow(), true);
  assert.equal(lim.allow(), false);
  t = 1500;
  assert.equal(lim.allow(), true);
});

test('hasSession e wipeAuth (persistência/invalidação da sessão)', () => {
  const dir = path.join(tmp(), 'auth');
  fs.mkdirSync(dir);
  assert.equal(lib.hasSession(dir), false); // sem creds
  fs.writeFileSync(path.join(dir, 'creds.json'), JSON.stringify({ registered: false }));
  assert.equal(lib.hasSession(dir), false); // não pareado
  fs.writeFileSync(path.join(dir, 'creds.json'), '{quebrado');
  assert.equal(lib.hasSession(dir), false); // corrompido
  fs.writeFileSync(path.join(dir, 'creds.json'), JSON.stringify({ registered: true }));
  assert.equal(lib.hasSession(dir), true); // pareado: reinício não pede novo pareamento
  fs.writeFileSync(path.join(dir, 'outra.json'), '{}');
  lib.wipeAuth(dir);
  assert.deepEqual(fs.readdirSync(dir), []);
  assert.equal(lib.hasSession(dir), false);
  if (process.platform !== 'win32') assert.equal(fs.statSync(dir).mode & 0o077, 0);
});

test('pick e resolveMakeSocket aceitam formatos ESM e CJS', () => {
  const fn = () => {};
  assert.equal(lib.resolveMakeSocket({ default: fn }), fn);
  assert.equal(lib.resolveMakeSocket({ default: { default: fn } }), fn);
  assert.equal(lib.resolveMakeSocket({ makeWASocket: fn }), fn);
  assert.equal(lib.resolveMakeSocket({}), undefined);
  assert.equal(lib.pick({ a: 1 }, 'a'), 1);
  assert.equal(lib.pick({ default: { a: 2 } }, 'a'), 2);
  assert.equal(lib.pick({}, 'a'), undefined);
});

test('identificadores: normalização e mapa lid -> telefone', () => {
  assert.equal(lib.normalizeJid('5511999999999:12@s.whatsapp.net'), '5511999999999@s.whatsapp.net');
  const map = lib.buildIdentityMap([
    { id: '111@lid', lid: '111@lid', phoneNumber: '5511999999999@s.whatsapp.net' },
    { id: '5521888888888@s.whatsapp.net' },
    { id: '222@lid' },
  ]);
  assert.equal(lib.canonicalJid('111@lid', map), '5511999999999@s.whatsapp.net');
  assert.equal(lib.canonicalJid('5521888888888@s.whatsapp.net', map), '5521888888888@s.whatsapp.net');
  assert.equal(lib.canonicalJid('222@lid', map), '222@lid'); // sem telefone conhecido: mantém
});

test('parseIncoming', () => {
  const base = (over = {}) => ({
    key: { remoteJid: '1203@g.us', participant: '5511@s.whatsapp.net', id: 'ABC', fromMe: false },
    message: { conversation: ' .ping ' },
    pushName: 'Ana',
    messageTimestamp: 1700000000,
    ...over,
  });
  const p = lib.parseIncoming(base(), 'bot@s.whatsapp.net');
  assert.equal(p.text, '.ping');
  assert.equal(p.sender, '5511@s.whatsapp.net');
  assert.equal(p.is_group, true);
  assert.equal(p.bot_id, 'bot@s.whatsapp.net');
  assert.equal(p.timestamp, 1700000000);

  const priv = lib.parseIncoming(base({ key: { remoteJid: '5511@s.whatsapp.net', id: 'X' } }));
  assert.equal(priv.is_group, false);
  assert.equal(priv.sender, '5511@s.whatsapp.net');

  assert.equal(lib.parseIncoming(base({ key: { remoteJid: 'status@broadcast', id: 'X' } })), null);
  // mensagem da própria conta (bot rodando no número do dono): vale em grupo, nunca em conversa privada com outra pessoa
  const own = lib.parseIncoming(base({ key: { remoteJid: '1203@g.us', id: 'OWN1', fromMe: true } }), 'bot@s.whatsapp.net');
  assert.equal(own.from_me, true);
  assert.equal(own.sender, 'bot@s.whatsapp.net');
  assert.equal(lib.parseIncoming(base({ key: { remoteJid: '5599@s.whatsapp.net', id: 'OWN2', fromMe: true } }), 'bot@s.whatsapp.net').from_me, true); // dono falando no privado: o Python só usa como sinal
  assert.equal(lib.parseIncoming(base({ key: { remoteJid: 'bot@s.whatsapp.net', id: 'OWN3', fromMe: true } }), 'bot@s.whatsapp.net').from_me, true);
  lib.rememberSent('OWN4'); // enviada pelo próprio bot: ignorada
  assert.equal(lib.parseIncoming(base({ key: { remoteJid: '1203@g.us', id: 'OWN4', fromMe: true } }), 'bot@s.whatsapp.net'), null);
  assert.equal(lib.parseIncoming(base({ message: { stickerMessage: {} } })), null);
  assert.equal(lib.parseIncoming(base({ key: { remoteJid: '1203@g.us', id: 'X' } })), null); // sem participante
  assert.equal(lib.parseIncoming({}), null);

  const wrapped = lib.parseIncoming(base({ message: { ephemeralMessage: { message: { extendedTextMessage: {
    text: '.perfil @5511',
    contextInfo: { mentionedJid: ['5511@s.whatsapp.net'], participant: '5522@s.whatsapp.net' },
  } } } } }));
  assert.equal(wrapped.text, '.perfil @5511');
  assert.deepEqual(wrapped.mentioned, ['5511@s.whatsapp.net']);
  assert.equal(wrapped.quoted_sender, '5522@s.whatsapp.net');

  const long = lib.parseIncoming(base({ messageTimestamp: { toNumber: () => 1700000123 } }));
  assert.equal(long.timestamp, 1700000123);
});

function fakeSock() {
  const calls = [];
  return {
    calls,
    sendMessage: async (...a) => calls.push(['send', ...a]),
    groupParticipantsUpdate: async (...a) => calls.push(['kick', ...a]),
    groupUpdateDescription: async (...a) => calls.push(['desc', ...a]),
    groupUpdateSubject: async (...a) => calls.push(['subject', ...a]),
    groupSettingUpdate: async (...a) => calls.push(['setting', ...a]),
  };
}
const immediate = lib.createSender(0, (e) => { throw e; }, async () => {});

test('perform envia texto com menção e cita a mensagem original', async () => {
  const sock = fakeSock();
  const original = { key: { id: 'Q' } };
  await lib.perform(sock, immediate, '1203@g.us',
    { text: 'oi', mentions: ['5511@s.whatsapp.net', 'lixo'], quote: true, actions: [] }, original);
  assert.equal(sock.calls.length, 1);
  assert.deepEqual(sock.calls[0][2], { text: 'oi', mentions: ['5511@s.whatsapp.net'] });
  assert.deepEqual(sock.calls[0][3], { quoted: original });
});

test('perform envia imagem em base64', async () => {
  const sock = fakeSock();
  await lib.perform(sock, immediate, '1203@g.us',
    { text: 'qr', image_base64: Buffer.from('abc').toString('base64'), quote: false, actions: [] }, null);
  assert.equal(Buffer.isBuffer(sock.calls[0][2].image), true);
  assert.equal(sock.calls[0][2].caption, 'qr');
});

test('perform executa kick/delete/descrição válidos', async () => {
  const sock = fakeSock();
  const chat = '1203@g.us';
  await lib.perform(sock, immediate, chat, { actions: [
    { type: 'kick', chat_id: chat, users: ['5511@s.whatsapp.net'] },
    { type: 'delete', chat_id: chat, message_id: 'M1', participant: '5511@s.whatsapp.net' },
    { type: 'set_description', chat_id: chat, text: 'nova descrição' },
  ] }, null);
  assert.deepEqual(sock.calls.map((c) => c[0]), ['kick', 'send', 'desc']);
  assert.deepEqual(sock.calls[0].slice(1), [chat, ['5511@s.whatsapp.net'], 'remove']);
  assert.equal(sock.calls[1][2].delete.id, 'M1');
});

test('perform renomeia e abre/fecha o grupo só com dados válidos', async () => {
  const sock = fakeSock();
  const chat = '1203@g.us';
  await lib.perform(sock, immediate, chat, { actions: [
    { type: 'set_subject', chat_id: chat, text: '  Turma 2026  ' },
    { type: 'set_announce', chat_id: chat, announce: true },
    { type: 'set_announce', chat_id: chat, announce: false },
    { type: 'set_subject', chat_id: chat, text: '   ' },
    { type: 'set_announce', chat_id: chat, announce: 'sim' },
    { type: 'set_subject', chat_id: '9@g.us', text: 'outro grupo' },
  ] }, null);
  assert.deepEqual(sock.calls, [['subject', chat, 'Turma 2026'], ['setting', chat, 'announcement'], ['setting', chat, 'not_announcement']]);
});

test('perform rejeita ações perigosas ou inválidas', async () => {
  const sock = fakeSock();
  const chat = '1203@g.us';
  await lib.perform(sock, immediate, chat, { actions: [
    { type: 'kick', chat_id: '9999@g.us', users: ['5511@s.whatsapp.net'] }, // outro grupo
    { type: 'kick', chat_id: '5511@s.whatsapp.net', users: ['5511@s.whatsapp.net'] }, // não é grupo
    { type: 'kick', chat_id: chat, users: ['nao-e-jid'] }, // usuário inválido
    { type: 'kick', chat_id: chat, users: [] },
    { type: 'logout', chat_id: chat }, // ação desconhecida
    { type: 'delete', chat_id: chat, message_id: 5, participant: '5511@s.whatsapp.net' },
    { type: 'set_description', chat_id: chat, text: 42 },
    null,
  ] }, null);
  assert.equal(sock.calls.length, 0);
});

test('perform limita a 5 usuários por remoção', async () => {
  const sock = fakeSock();
  const chat = '1203@g.us';
  const users = Array.from({ length: 9 }, (_, i) => `55${i}@s.whatsapp.net`);
  await lib.perform(sock, immediate, chat, { actions: [{ type: 'kick', chat_id: chat, users }] }, null);
  assert.equal(sock.calls[0][2].length, 5);
});

test('createSender mantém a ordem e isola erros', async () => {
  const order = [];
  const errors = [];
  const enqueue = lib.createSender(0, (e) => errors.push(e.message), async () => {});
  enqueue(async () => order.push(1));
  enqueue(async () => { throw new Error('falhou'); });
  await enqueue(async () => order.push(3));
  assert.deepEqual(order, [1, 3]);
  assert.deepEqual(errors, ['falhou']);
});

test('perform: ações de controle (shutdown/logout) rodam depois da resposta e só as conhecidas', async () => {
  const order = [];
  const sock = { sendMessage: async () => { order.push('enviou'); return { key: { id: 'S1' } }; } };
  const enqueue = (fn) => Promise.resolve().then(fn);
  const control = { shutdown: async () => order.push('shutdown'), logout: async () => order.push('logout') };
  await lib.perform(sock, enqueue, '1203@g.us', { text: 'tchau', actions: [{ type: 'shutdown' }, { type: 'inventada' }] }, null, control);
  assert.deepEqual(order, ['enviou', 'shutdown']);
  await lib.perform(sock, enqueue, '1203@g.us', { text: '', actions: [{ type: 'logout' }] }, null, {}); // sem handler: ignora
  assert.deepEqual(order, ['enviou', 'shutdown']);
});

test('mídia: dicas de áudio/imagem e limites', () => {
  const base = (message) => ({ key: { remoteJid: '1203@g.us', participant: '5511@s.whatsapp.net', id: 'M1' }, message });
  const a = lib.parseIncoming(base({ audioMessage: { mimetype: 'audio/ogg; codecs=opus', seconds: 12, fileLength: 20000 } }));
  assert.equal(a.text, '');
  assert.deepEqual(a.media_hint, { kind: 'audio', mime: 'audio/ogg; codecs=opus', seconds: 12, size: 20000 });
  assert.equal(lib.mediaAllowed(a.media_hint), true);
  assert.equal(lib.mediaAllowed({ kind: 'audio', seconds: 900, size: 100 }), false); // longo demais
  assert.equal(lib.mediaAllowed({ kind: 'audio', seconds: 5, size: 99_000_000 }), false); // pesado demais
  assert.equal(lib.mediaAllowed({ kind: 'video', seconds: 5, size: 10 }), false);
  const img = lib.parseIncoming(base({ imageMessage: { mimetype: 'image/jpeg', caption: ' olha ', fileLength: { toNumber: () => 1234 } } }));
  assert.equal(img.text, 'olha');
  assert.equal(img.media_hint.size, 1234);
  assert.equal(lib.parseIncoming(base({ stickerMessage: {} })), null);
});

test('perform envia áudio (voz) e imagem', async () => {
  const sent = [];
  const sock = { sendMessage: async (jid, content) => { sent.push({ jid, content }); return { key: { id: 'SENT1' } }; } };
  const enqueue = (fn) => fn();
  await lib.perform(sock, enqueue, '1203@g.us', { audio_base64: Buffer.from('OGG').toString('base64'), audio_mimetype: 'audio/ogg; codecs=opus', ptt: true }, null);
  assert.equal(sent[0].content.ptt, true);
  assert.equal(sent[0].content.mimetype, 'audio/ogg; codecs=opus');
  assert.equal(sent[0].content.audio.toString(), 'OGG');
  await lib.perform(sock, enqueue, '1203@g.us', { audio_base64: 'QUJD', audio_mimetype: 'text/html', ptt: false }, null);
  assert.equal(sent[1].content.mimetype, 'audio/ogg; codecs=opus'); // mimetype estranho é substituído
  assert.equal(sent[1].content.ptt, false);
  await lib.perform(sock, enqueue, '1203@g.us', { image_base64: 'SU1H', text: 'legenda' }, null);
  assert.equal(sent[2].content.caption, 'legenda');
  // o id enviado é lembrado: eco da própria mensagem nunca vira comando
  const echo = lib.parseIncoming({ key: { remoteJid: '1203@g.us', id: 'SENT1', fromMe: true }, message: { conversation: '.ping' } }, 'bot@s.whatsapp.net');
  assert.equal(echo, null);
});

test('getSent devolve o conteúdo enviado para reenvio e esquece o antigo', () => {
  lib.rememberSent('G1', { conversation: 'oi' });
  assert.deepEqual(lib.getSent('G1'), { conversation: 'oi' });
  assert.equal(lib.getSent('NAO-EXISTE'), undefined);
  for (let i = 0; i < 400; i++) lib.rememberSent(`X${i}`, { conversation: String(i) });
  assert.equal(lib.getSent('G1'), undefined); // limite de 300 mensagens guardadas
  assert.deepEqual(lib.getSent('X399'), { conversation: '399' });
});

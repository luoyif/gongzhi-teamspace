// Dependency-free UI state helpers; shared by browser code and Node regressions.
export function nextMentionIndex(items, current, direction = 1) {
  if (!Array.isArray(items) || !items.length) return -1;
  const step = direction < 0 ? -1 : 1;
  let index = Number.isInteger(current) && current >= 0 && current < items.length
    ? current : (step > 0 ? -1 : 0);
  for (let n = 0; n < items.length; n++) {
    index = (index + step + items.length) % items.length;
    if (items[index].type !== 'document' || items[index].usable) return index;
  }
  return -1;
}

export class SSEFrames {
  constructor() { this.buffer = ''; }
  push(text) {
    this.buffer += text;
    if (this.buffer.length > 8000000) throw new Error('流式事件超过允许大小');
    const frames = [];
    let match;
    while ((match = /\r\n\r\n|\n\n|\r\r/.exec(this.buffer))) {
      const block = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);
      let event = 'message', id = null;
      const data = [];
      for (const line of block.split(/\r\n|\r|\n/)) {
        if (!line || line.startsWith(':')) continue;
        const at = line.indexOf(':');
        const name = at < 0 ? line : line.slice(0, at);
        let value = at < 0 ? '' : line.slice(at + 1);
        if (value.startsWith(' ')) value = value.slice(1);
        if (name === 'event') event = value;
        if (name === 'id' && !value.includes('\0')) id = value;
        if (name === 'data') data.push(value);
      }
      if (data.length) frames.push({event, id, data: data.join('\n')});
    }
    return frames;
  }
}

export function traceOverview(events) {
  const start = events.find(e => e.event === 'run.start')?.payload || {};
  const request = events.find(e => e.event === 'model.request')?.payload || {};
  const end = [...events].reverse().find(e => e.event === 'run.end')?.payload || {};
  const finished = [...events].reverse().find(e => e.event === 'agent.finished')?.payload || {};
  return {agent: start.agent_name || start.config_snapshot?.name || '历史运行',
    revision: start.agent_revision ?? null, model: request.model || '未记录',
    modelSteps: events.filter(e => e.event === 'model.start').length,
    toolResults: events.filter(e => e.event === 'tool.result').length,
    humanMessages: events.filter(e => e.event === 'human.message').length,
    status: end.status || '运行中／尚未完整加载', usage: end.usage || finished.usage || null};
}

'use strict';

(function () {
  const COLUMN_HEADERS = {
    date:    'Date',
    time:    'Time (UTC)',
    call:    'Callsign',
    band:    'Band',
    mode:    'Mode',
    rst:     'RST',
    name:    'Name',
    comment: 'Comment',
    siginfo: 'Program',
  };

  function parseAdif(text) {
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

    // Strip header section (everything up to and including <EOH>)
    const eohMatch = text.match(/<eoh>/i);
    if (eohMatch) {
      text = text.slice(eohMatch.index + eohMatch[0].length);
    }

    const rawRecords = text.split(/<eor>/i);
    const records = [];

    for (const raw of rawRecords) {
      const trimmed = raw.trim();
      if (!trimmed) continue;

      const record = {};
      // Matches <FIELDNAME:LENGTH> or <FIELDNAME:LENGTH:TYPE>
      const tokenPattern = /<([A-Z0-9_]+):(\d+)(?::[^>]+)?>/gi;
      let match;

      while ((match = tokenPattern.exec(trimmed)) !== null) {
        const fieldName = match[1].toUpperCase();
        const length = parseInt(match[2], 10);
        const valueStart = match.index + match[0].length;
        const value = trimmed.substr(valueStart, length).trim();
        record[fieldName] = value;
      }

      if (Object.keys(record).length > 0) {
        records.push(record);
      }
    }

    return records;
  }

  function formatDate(val) {
    if (!val || val.length < 8) return val || '—';
    return val.slice(0, 4) + '-' + val.slice(4, 6) + '-' + val.slice(6, 8);
  }

  function formatTime(val) {
    if (!val || val.length < 4) return val || '—';
    return val.slice(0, 2) + ':' + val.slice(2, 4);
  }

  function deriveRst(record) {
    const sent = record.RST_SENT;
    const rcvd = record.RST_RCVD;
    if (sent && rcvd) return sent + ' / ' + rcvd;
    if (sent) return sent;
    if (rcvd) return rcvd;
    return '—';
  }

  function deriveSigInfo(record) {
    if (record.MY_SIG && record.MY_SIG_INFO) {
      return record.MY_SIG.toUpperCase() + ': ' + record.MY_SIG_INFO;
    }
    if (record.SIG && record.SIG_INFO) {
      return record.SIG.toUpperCase() + ': ' + record.SIG_INFO;
    }
    if (record.MY_SIG_INFO) return record.MY_SIG_INFO;
    if (record.SIG_INFO) return record.SIG_INFO;
    return '—';
  }

  function getColumnValue(record, col) {
    switch (col) {
      case 'date':    return formatDate(record.QSO_DATE);
      case 'time':    return formatTime(record.TIME_ON);
      case 'call':    return record.CALL || '—';
      case 'band':    return record.BAND || '—';
      case 'mode':    return record.MODE || '—';
      case 'rst':     return deriveRst(record);
      case 'name':    return record.NAME || '—';
      case 'comment': return record.COMMENT || '—';
      case 'siginfo': return deriveSigInfo(record);
      default:        return record[col.toUpperCase()] || '—';
    }
  }

  function renderTable(container, records, columns, caption) {
    if (records.length === 0) {
      container.innerHTML = '<p>No QSOs found in log file.</p>';
      return;
    }

    const table = document.createElement('table');

    if (caption) {
      const cap = document.createElement('caption');
      cap.textContent = caption;
      table.appendChild(cap);
    }

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    for (const col of columns) {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = COLUMN_HEADERS[col] || col;
      headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    for (const record of records) {
      const tr = document.createElement('tr');
      for (const col of columns) {
        const td = document.createElement('td');
        td.textContent = getColumnValue(record, col);
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);

    container.innerHTML = '';
    container.appendChild(table);
  }

  function isSameOrigin(url) {
    if (!url) return false;
    if (url.startsWith('/') || url.startsWith('./') || url.startsWith('../')) return true;
    try {
      return new URL(url).origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  async function loadAdifTable(container) {
    const url = container.dataset.adifUrl;
    if (!isSameOrigin(url)) {
      const msg = document.createElement('p');
      msg.textContent = 'ADIF log must be served from the same site.';
      container.appendChild(msg);
      return;
    }
    const columns = (container.dataset.columns || 'date,time,call,band,mode,rst')
      .split(',')
      .map(function (c) { return c.trim(); })
      .filter(Boolean);
    const caption = container.dataset.caption || '';

    container.innerHTML = '<p>Loading log\u2026</p>';

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }
      const text = await response.text();
      const records = parseAdif(text);
      renderTable(container, records, columns, caption);
    } catch (err) {
      const msg = document.createElement('p');
      msg.textContent = 'Failed to load log: ' + err.message;
      container.appendChild(msg);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var containers = document.querySelectorAll('.ham-adif-table[data-adif-url]');
    containers.forEach(loadAdifTable);
  });
}());

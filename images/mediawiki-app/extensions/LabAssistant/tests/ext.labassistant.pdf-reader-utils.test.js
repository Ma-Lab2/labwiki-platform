const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildLiteratureGuideEditUrl,
  buildAssistantQuotePrompt,
  clampPdfPageNumber,
  isLiteratureGuideTitle,
  normalizePdfReaderSource
} = require('../modules/ext.labassistant.pdf-reader-utils.js');

test('isLiteratureGuideTitle detects literature guide pages conservatively', () => {
  assert.equal(isLiteratureGuideTitle('文献导读/Macchi2013'), true);
  assert.equal(isLiteratureGuideTitle('Theory:TNSA'), false);
  assert.equal(isLiteratureGuideTitle(''), false);
});

test('normalizePdfReaderSource keeps wiki file and assistant attachment metadata', () => {
  assert.deepEqual(
    normalizePdfReaderSource({
      type: 'wiki_file',
      fileTitle: 'File:Macchi2013.pdf',
      url: '/wiki/Special:Redirect/file/Macchi2013.pdf',
      fileLabel: 'Macchi2013.pdf',
      pageTitle: '文献导读/Macchi2013'
    }),
    {
      type: 'wiki_file',
      fileTitle: 'File:Macchi2013.pdf',
      url: '/wiki/Special:Redirect/file/Macchi2013.pdf',
      fileLabel: 'Macchi2013.pdf',
      pageTitle: '文献导读/Macchi2013'
    }
  );

  assert.deepEqual(
    normalizePdfReaderSource({
      type: 'assistant_attachment',
      attachmentId: 'att-001',
      url: '/tools/assistant/api/attachments/att-001/content',
      fileLabel: 'shot-note.pdf'
    }),
    {
      type: 'assistant_attachment',
      attachmentId: 'att-001',
      url: '/tools/assistant/api/attachments/att-001/content',
      fileLabel: 'shot-note.pdf',
      pageTitle: ''
    }
  );
});

test('buildAssistantQuotePrompt includes file label, page number and selected text', () => {
  assert.equal(
    buildAssistantQuotePrompt({
      pageTitle: '文献导读/Macchi2013',
      fileLabel: 'Macchi2013.pdf',
      pageNumber: 7,
      selectedText: 'Target normal sheath acceleration dominates for thick targets.'
    }),
    [
      '请基于以下 PDF 选区继续解释，并结合当前 Wiki 页面上下文回答。',
      '当前页面：文献导读/Macchi2013',
      'PDF 文件：Macchi2013.pdf',
      'PDF 页码：7',
      '引用选区：',
      'Target normal sheath acceleration dominates for thick targets.'
    ].join('\n')
  );
});

test('clampPdfPageNumber keeps page navigation at 1 or above', () => {
  assert.equal(clampPdfPageNumber(5, -1), 4);
  assert.equal(clampPdfPageNumber(1, -1), 1);
  assert.equal(clampPdfPageNumber('7', 2), 9);
  assert.equal(clampPdfPageNumber('', 0), 1);
});

test('buildLiteratureGuideEditUrl targets the PageForms edit entry for literature pages', () => {
  assert.equal(
    buildLiteratureGuideEditUrl('文献导读/Macchi2013', {
      util: {
        getUrl: (title) => '/wiki/' + title
      }
    }),
    '/wiki/Special:编辑表格/文献导读/文献导读/Macchi2013'
  );
  assert.equal(
    buildLiteratureGuideEditUrl('文献导读/Macchi2013'),
    '/wiki/Special:%E7%BC%96%E8%BE%91%E8%A1%A8%E6%A0%BC/%E6%96%87%E7%8C%AE%E5%AF%BC%E8%AF%BB/%E6%96%87%E7%8C%AE%E5%AF%BC%E8%AF%BB/Macchi2013'
  );
  assert.equal(buildLiteratureGuideEditUrl('Theory:TNSA'), '');
});

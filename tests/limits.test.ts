import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateAttachments} from '../lib/limits.ts';
const pdf={name:'book.pdf',type:'application/pdf',data:'data:application/pdf;base64,JVBERi0='};
const image={name:'page.png',type:'image/png',data:'data:image/png;base64,aGVsbG8='};
test('accepts a complete PDF without page selection',()=>assert.doesNotThrow(()=>validateAttachments([pdf])));
test('accepts five images',()=>assert.doesNotThrow(()=>validateAttachments(Array(5).fill(image))));
test('rejects mixed PDF/image and six images',()=>{assert.throws(()=>validateAttachments([pdf,image]));assert.throws(()=>validateAttachments(Array(6).fill(image)));});
test('rejects forged data URLs and oversize payloads',()=>{assert.throws(()=>validateAttachments([{...pdf,data:image.data}]));assert.throws(()=>validateAttachments([{...pdf,data:'data:application/pdf;base64,'+'a'.repeat(4_000_000)}]));});

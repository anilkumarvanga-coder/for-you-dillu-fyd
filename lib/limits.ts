export const MAX_BODY = 4_000_000;
export const MAX_FILE = 2_800_000;
export const MAX_IMAGES = 5;
export type Attachment = { name: string; type: string; data: string };
export function validateAttachments(files: Attachment[]) {
  if (files.length > MAX_IMAGES) throw new Error('Choose one PDF or up to five images.');
  const pdfs = files.filter(f => f.type === 'application/pdf');
  if (pdfs.length && files.length !== 1) throw new Error('Send one complete PDF at a time.');
  for (const file of files) {
    if (!['application/pdf', 'image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Use PDF, JPG, PNG, or WebP.');
    const prefix = `data:${file.type};base64,`;
    if (!file.data.startsWith(prefix)) throw new Error('Invalid attachment encoding.');
    const encoded = file.data.slice(prefix.length);
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(encoded) || encoded.length % 4) throw new Error('Invalid attachment data.');
    if (encoded.length * 3 / 4 > MAX_FILE + 2) throw new Error('Each file must be under 2.8 MB.');
  }
}

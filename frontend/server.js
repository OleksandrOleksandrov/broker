import express from 'express';
import multer from 'multer';
import FormData from 'form-data';
import fetch from 'node-fetch';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const upload = multer({ storage: multer.memoryStorage() });
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://127.0.0.1:8000';

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// Проксі-ендпоінт відправки файлу на FastAPI backend
app.post('/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Файл не завантажено' });
    }

    const formData = new FormData();
    formData.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype,
    });

    const response = await fetch(`${FASTAPI_URL}/api/parse-invoice`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Помилка FastAPI: ${errText}`);
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/upload-cmr', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Файл не завантажено' });
    }

    const formData = new FormData();
    formData.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype,
    });

    const response = await fetch(`${FASTAPI_URL}/api/parse-cmr`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Помилка FastAPI: ${errText}`);
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/upload-transport-documents', upload.fields([
  { name: 'invoice_file', maxCount: 1 },
  { name: 'application_file', maxCount: 1 },
  { name: 'cmr_file', maxCount: 1 },
]), async (req, res) => {
  try {
    const files = req.files;
    const invoiceFile = files?.invoice_file?.[0];
    const applicationFile = files?.application_file?.[0];
    const cmrFile = files?.cmr_file?.[0];
    if (!invoiceFile || !applicationFile || !cmrFile) {
      return res.status(400).json({ error: 'Потрібні всі три файли' });
    }

    const formData = new FormData();
    for (const [field, file] of [
      ['invoice_file', invoiceFile],
      ['application_file', applicationFile],
      ['cmr_file', cmrFile],
    ]) {
      formData.append(field, file.buffer, {
        filename: file.originalname,
        contentType: file.mimetype,
      });
    }
    if (req.body.parse_uktzed) {
      formData.append('parse_uktzed', req.body.parse_uktzed);
    }

    const response = await fetch(`${FASTAPI_URL}/api/parse-transport-documents`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`Помилка FastAPI: ${await response.text()}`);
    }
    res.json(await response.json());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Node.js Frontend запущено на http://localhost:${PORT}`);
});

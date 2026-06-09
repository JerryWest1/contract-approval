import { google } from 'googleapis';
import { Readable } from 'node:stream';

/**
 * Build an authenticated Google Drive client from a service account JSON key.
 * The service account must be added as a member (Content manager or higher)
 * of the LIGHTHOUSE shared drive, otherwise uploads will 404/403.
 */
export function makeDriveClient(serviceAccountJson) {
    const credentials =
        typeof serviceAccountJson === 'string'
            ? JSON.parse(serviceAccountJson)
            : serviceAccountJson;

    const auth = new google.auth.GoogleAuth({
        credentials,
        scopes: ['https://www.googleapis.com/auth/drive'],
    });

    return google.drive({ version: 'v3', auth });
}

/**
 * Upload a PDF buffer to a folder inside a shared drive.
 * Returns the created file's id and webViewLink.
 */
export async function uploadPdf(drive, { buffer, fileName, folderId }) {
    const res = await drive.files.create({
        // Required for shared drives.
        supportsAllDrives: true,
        requestBody: {
            name: fileName,
            parents: [folderId],
            mimeType: 'application/pdf',
        },
        media: {
            mimeType: 'application/pdf',
            body: Readable.from(buffer),
        },
        fields: 'id, name, webViewLink',
    });

    return res.data;
}

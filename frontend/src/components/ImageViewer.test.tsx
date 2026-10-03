import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { forgetImage, rememberImage } from '../lib/imageCache';
import type { Attachment } from '../state/types';
import { AttachmentPreview } from './MessageItem';

const image: Attachment = {
  fileId: 'img-1',
  name: 'chart.png',
  kind: 'image',
  sizeBytes: 4096,
  previewUrl: 'data:image/jpeg;base64,THUMB',
};

afterEach(() => forgetImage(image.fileId));

describe('AttachmentPreview image viewer', () => {
  it('opens the full-size original when the thumbnail is clicked', async () => {
    rememberImage(image.fileId, 'blob:original');
    render(<AttachmentPreview attachment={image} />);
    const user = userEvent.setup();

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'View chart.png' }));

    const dialog = screen.getByRole('dialog', { name: 'Image: chart.png' });
    expect(dialog).toHaveAttribute('open');
    expect(screen.getAllByRole('img', { name: 'chart.png' })[1]).toHaveAttribute('src', 'blob:original');
    expect(screen.queryByText(/Showing a preview/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close image' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('falls back to the stored thumbnail after a reload', async () => {
    render(<AttachmentPreview attachment={image} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'View chart.png' }));

    expect(screen.getAllByRole('img', { name: 'chart.png' })[1]).toHaveAttribute('src', image.previewUrl);
    expect(screen.getByText(/Showing a preview/)).toBeInTheDocument();
  });

  it('falls back to the thumbnail when the original no longer loads', async () => {
    rememberImage(image.fileId, 'blob:revoked');
    render(<AttachmentPreview attachment={image} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'View chart.png' }));

    fireEvent.error(screen.getAllByRole('img', { name: 'chart.png' })[1]);
    expect(screen.getAllByRole('img', { name: 'chart.png' })[1]).toHaveAttribute('src', image.previewUrl);
  });

  it('closes on a backdrop click but not on a click inside the image', async () => {
    render(<AttachmentPreview attachment={image} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'View chart.png' }));

    await user.click(screen.getAllByRole('img', { name: 'chart.png' })[1]);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('dialog'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('keeps documents as non-clickable chips', () => {
    render(
      <AttachmentPreview
        attachment={{ fileId: 'doc-1', name: 'report.pdf', kind: 'document', sizeBytes: 2048 }}
      />,
    );
    expect(screen.getByText('report.pdf')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});

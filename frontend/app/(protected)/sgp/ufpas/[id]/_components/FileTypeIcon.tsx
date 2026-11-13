import { FileImage, FileText, File as FileIcon } from "lucide-react";

type Props = {
  contentType: string;
  className?: string;
};

export function FileTypeIcon({ contentType, className = "h-4 w-4" }: Props) {
  if (contentType === "application/pdf") {
    return <FileText className={`${className} text-error-text`} aria-label="PDF" />;
  }
  if (contentType === "image/jpeg" || contentType === "image/png") {
    return <FileImage className={`${className} text-primary`} aria-label="Imagem" />;
  }
  return <FileIcon className={`${className} text-text-muted`} aria-label="Arquivo" />;
}

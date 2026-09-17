export interface FilePickerProps {
  label: string;
  accept?: string;
  onChange: (file: File | null) => void;
  selectedFile: File | null;
  disabled?: boolean;
}
export interface FilePickerProps<T extends File | File[] | null = File | null> {
  label: string;
  accept?: string;
  onChange: (value: T) => void;
  selectedFile: T;
  multiple?: boolean;
  disabled?: boolean;
}

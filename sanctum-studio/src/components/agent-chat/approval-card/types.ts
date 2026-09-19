export type ApprovalQuestion = {
  q: string;
  type: "radio" | "check";
  options: string[];
};

export type ApprovalLabels = {
  skip: string;
  continue: string;
  send: string;
  customPlaceholder: string;
  sentMessage: string;
};

export interface ApprovalCardProps {
  questions?: ApprovalQuestion[];
  labels?: Partial<ApprovalLabels>;
  onSubmitted?: (answers: Record<number, number[]>) => void;
  onAnswerChange?: (questionIndex: number, answer: number[]) => void;
  resettable?: boolean;
  variant?: string;
  className?: string;
}

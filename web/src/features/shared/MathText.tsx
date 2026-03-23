import { useEffect, useRef } from "react";

import { enhanceMathContent } from "../../app/lib/markdown";

interface MathTextProps {
  text: string;
  className?: string;
}

export function MathText({ text, className }: MathTextProps) {
  const elementRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) {
      return;
    }

    element.textContent = text;
    enhanceMathContent(element);
  }, [text]);

  return <span ref={elementRef} className={className} data-raw-text={text} />;
}

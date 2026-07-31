import { forwardRef, useId, type InputHTMLAttributes } from "react";

import { fieldMessage } from "../../lib/field-message";
import { cn } from "../../lib/utils";
import { Input } from "./input";

export interface GuidedInputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** One line under the field: what may be typed, and the range when bounded. */
  hint?: string;
}

/**
 * An input that says what it accepts before and after a mistake.
 *
 * The hint is always visible so the rule does not have to be discovered by
 * failing, and a rejected value replaces the browser's default wording with the
 * same rule stated as a sentence. The custom message is cleared on every edit;
 * otherwise a field would stay rejected after being corrected.
 */
export const GuidedInput = forwardRef<HTMLInputElement, GuidedInputProps>(
  (
    {
      hint,
      className,
      onInvalid,
      onInput,
      "aria-describedby": describedBy,
      ...props
    },
    ref,
  ) => {
    const hintId = useId();
    return (
      <>
        <Input
          {...props}
          ref={ref}
          className={cn(className)}
          aria-describedby={hint ? hintId : describedBy}
          onInvalid={(event) => {
            event.currentTarget.setCustomValidity(fieldMessage(event.currentTarget));
            onInvalid?.(event);
          }}
          onInput={(event) => {
            event.currentTarget.setCustomValidity("");
            onInput?.(event);
          }}
        />
        {hint && (
          <span
            id={hintId}
            className="mt-1 block text-[10px] font-normal leading-relaxed text-muted-foreground"
          >
            {hint}
          </span>
        )}
      </>
    );
  },
);
GuidedInput.displayName = "GuidedInput";

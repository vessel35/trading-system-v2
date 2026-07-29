import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { cn } from "../../lib/utils";
import { Button } from "./button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./dialog";
import { Input } from "./input";

export interface DateTimePickerFieldProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  "aria-label"?: string;
  id?: string;
  "aria-invalid"?: boolean;
}

const weekDays = ["일", "월", "화", "수", "목", "금", "토"];
const monthFormatter = new Intl.DateTimeFormat("ko-KR", {
  year: "numeric",
  month: "long",
});

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function dateKey(value: Date): string {
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

function dateLabel(value: Date): string {
  return `${value.getFullYear()}년 ${value.getMonth() + 1}월 ${value.getDate()}일 선택`;
}

function sameDay(left: Date, right: Date): boolean {
  return dateKey(left) === dateKey(right);
}

function dateAtNoon(year: number, month: number, day: number): Date {
  return new Date(year, month, day, 12);
}

function addDays(value: Date, amount: number): Date {
  return dateAtNoon(value.getFullYear(), value.getMonth(), value.getDate() + amount);
}

function addMonths(value: Date, amount: number): Date {
  return dateAtNoon(value.getFullYear(), value.getMonth() + amount, 1);
}

function shiftMonths(value: Date, amount: number): Date {
  const month = value.getMonth() + amount;
  // Day 0 of the following month is the last day of the target month, which keeps
  // 1월 31일 from spilling into 3월 when a shorter month is the destination.
  const lastDay = new Date(value.getFullYear(), month + 1, 0).getDate();
  return dateAtNoon(value.getFullYear(), month, Math.min(value.getDate(), lastDay));
}

function parseValue(value: string): { date: Date; time: string } | null {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;

  const [, yearText, monthText, dayText, hourText, minuteText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const date = dateAtNoon(year, month - 1, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day ||
    hour > 23 ||
    minute > 59
  ) {
    return null;
  }

  return { date, time: `${hourText}:${minuteText}` };
}

function initialDraft(value: string): { date: Date; time: string } {
  const parsed = parseValue(value);
  if (parsed) return parsed;

  const now = new Date();
  return {
    date: dateAtNoon(now.getFullYear(), now.getMonth(), now.getDate()),
    time: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
  };
}

function contractValue(date: Date, time: string): string {
  return `${dateKey(date)}T${time}`;
}

function monthGrid(viewMonth: Date): Date[] {
  const first = dateAtNoon(viewMonth.getFullYear(), viewMonth.getMonth(), 1);
  const gridStart = addDays(first, -first.getDay());
  return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
}

export function DateTimePickerField({
  value,
  onChange,
  label,
  "aria-label": ariaLabel,
  id,
  "aria-invalid": ariaInvalid,
}: DateTimePickerFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? `date-time-picker-${generatedId.replaceAll(":", "")}`;
  const timeId = `${fieldId}-time`;
  const accessibleLabel = ariaLabel ?? label ?? "날짜 및 시간";
  const [open, setOpen] = useState(false);
  const initial = initialDraft(value);
  const [selectedDate, setSelectedDate] = useState(initial.date);
  const [selectedTime, setSelectedTime] = useState(initial.time);
  const [viewMonth, setViewMonth] = useState(
    dateAtNoon(initial.date.getFullYear(), initial.date.getMonth(), 1),
  );
  const dayButtons = useRef(new Map<string, HTMLButtonElement>());
  const today = new Date();

  useEffect(() => {
    if (!open) return;
    dayButtons.current.get(dateKey(selectedDate))?.focus();
  }, [open, selectedDate, viewMonth]);

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      const next = initialDraft(value);
      setSelectedDate(next.date);
      setSelectedTime(next.time);
      setViewMonth(dateAtNoon(next.date.getFullYear(), next.date.getMonth(), 1));
    }
    setOpen(nextOpen);
  }

  function selectDate(date: Date) {
    setSelectedDate(date);
    setViewMonth(dateAtNoon(date.getFullYear(), date.getMonth(), 1));
  }

  function handleDayKeyDown(event: KeyboardEvent<HTMLButtonElement>, date: Date) {
    const dayIncrements: Record<string, number> = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -7,
      ArrowDown: 7,
    };
    const dayIncrement = dayIncrements[event.key];
    if (dayIncrement !== undefined) {
      event.preventDefault();
      selectDate(addDays(date, dayIncrement));
      return;
    }

    // PageUp/PageDown step a month, and with Shift a year, so a multi-year backtest
    // window is reachable from the keyboard without clicking through every month.
    const pageDirections: Record<string, number> = { PageUp: -1, PageDown: 1 };
    const pageDirection = pageDirections[event.key];
    if (pageDirection === undefined) return;
    event.preventDefault();
    selectDate(shiftMonths(date, pageDirection * (event.shiftKey ? 12 : 1)));
  }

  const weeks = monthGrid(viewMonth);
  const selectedDateIsVisible = weeks.some((date) => sameDay(date, selectedDate));
  const focusableDate = selectedDateIsVisible
    ? selectedDate
    : dateAtNoon(viewMonth.getFullYear(), viewMonth.getMonth(), 1);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button
          id={fieldId}
          type="button"
          variant="outline"
          aria-label={accessibleLabel}
          aria-invalid={ariaInvalid}
          className="w-full justify-start gap-2 bg-background/70 px-3 font-normal tabular-nums"
        >
          <CalendarDays className="h-4 w-4 text-muted-foreground" />
          {value ? value.replace("T", " ") : "날짜와 시간을 선택하세요"}
        </Button>
      </DialogTrigger>
      <DialogContent
        className="top-[5vh] max-h-[90vh] max-w-md overflow-y-auto"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          dayButtons.current.get(dateKey(selectedDate))?.focus();
        }}
      >
        <div>
          <DialogTitle>{accessibleLabel} 선택</DialogTitle>
          <DialogDescription className="mt-1">
            날짜와 시간을 고른 뒤 선택 완료를 눌러 확정하세요.
          </DialogDescription>
        </div>

        <div className="rounded-lg border bg-background/40 p-3">
          <div className="mb-3 flex items-center justify-between gap-1">
            <div className="flex items-center">
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label="이전 해"
                onClick={() => setViewMonth((current) => addMonths(current, -12))}
              >
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label="이전 달"
                onClick={() => setViewMonth((current) => addMonths(current, -1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </div>
            <div className="font-medium" aria-live="polite">
              {monthFormatter.format(viewMonth)}
            </div>
            <div className="flex items-center">
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label="다음 달"
                onClick={() => setViewMonth((current) => addMonths(current, 1))}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label="다음 해"
                onClick={() => setViewMonth((current) => addMonths(current, 12))}
              >
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div role="grid" aria-label="날짜 선택" className="space-y-1">
            <div role="row" className="grid grid-cols-7 gap-1">
              {weekDays.map((day) => (
                <div
                  key={day}
                  role="columnheader"
                  className="py-1 text-center text-xs font-medium text-muted-foreground"
                >
                  {day}
                </div>
              ))}
            </div>
            {Array.from({ length: 6 }, (_, rowIndex) => (
              <div key={rowIndex} role="row" className="grid grid-cols-7 gap-1">
                {weeks.slice(rowIndex * 7, rowIndex * 7 + 7).map((date) => {
                  const selected = sameDay(date, selectedDate);
                  const inMonth = date.getMonth() === viewMonth.getMonth();
                  const isToday = sameDay(date, today);
                  return (
                    <div
                      key={dateKey(date)}
                      role="gridcell"
                      aria-selected={selected}
                    >
                      <button
                        ref={(node) => {
                          if (node) dayButtons.current.set(dateKey(date), node);
                          else dayButtons.current.delete(dateKey(date));
                        }}
                        type="button"
                        aria-label={dateLabel(date)}
                        aria-current={isToday ? "date" : undefined}
                        tabIndex={sameDay(date, focusableDate) ? 0 : -1}
                        className={cn(
                          "relative flex h-9 w-full items-center justify-center rounded-md text-sm outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                          !inMonth && "text-muted-foreground/45",
                          selected &&
                            "bg-primary font-semibold text-primary-foreground hover:bg-primary/90",
                          isToday &&
                            !selected &&
                            "border border-primary/70 font-semibold text-primary",
                        )}
                        onClick={() => selectDate(date)}
                        onKeyDown={(event) => handleDayKeyDown(event, date)}
                      >
                        {date.getDate()}
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor={timeId} className="text-sm font-medium">
            시간
          </label>
          <Input
            id={timeId}
            type="time"
            step={60}
            value={selectedTime}
            onChange={(event) => setSelectedTime(event.target.value)}
            required
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => setOpen(false)}>
            취소
          </Button>
          <Button
            type="button"
            disabled={!/^\d{2}:\d{2}$/.test(selectedTime)}
            onClick={() => {
              onChange(contractValue(selectedDate, selectedTime));
              setOpen(false);
            }}
          >
            선택 완료
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

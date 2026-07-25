import { LoaderCircle, Plus, Tag, X } from "lucide-react";
import { type FormEvent, useState } from "react";

import type { TagInput } from "../api/client";
import {
  useAddRunTag,
  useRemoveRunTag,
  useRunTags,
} from "../hooks/use-p2b";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

const tagTypes: TagInput["tag_type"][] = [
  "classification",
  "purpose",
  "weakness",
  "improvement",
  "usability",
];

export function RunTags({ runId }: { runId: string }) {
  const tags = useRunTags(runId);
  const addTag = useAddRunTag(runId);
  const removeTag = useRemoveRunTag(runId);
  const [tagType, setTagType] = useState<TagInput["tag_type"]>("classification");
  const [tagValue, setTagValue] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = tagValue.trim();
    if (!value) return;
    addTag.mutate(
      { tag_type: tagType, tag_value: value },
      { onSuccess: () => setTagValue("") },
    );
  }

  const error = addTag.error ?? removeTag.error ?? tags.error;

  return (
    <section className="mt-5 border-t pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <Tag className="h-3.5 w-3.5 text-teal-400" />
        <p className="text-xs font-semibold">실행 태그</p>
        {tags.isLoading && <LoaderCircle className="h-3 w-3 animate-spin" />}
        {(tags.data?.data ?? []).map((tag) => (
          <Badge key={tag.tag_id} variant="secondary" className="gap-1">
            <span className="text-muted-foreground">{tag.tag_type}</span>
            {tag.tag_value}
            <button
              type="button"
              aria-label={`${tag.tag_value} 태그 삭제`}
              disabled={removeTag.isPending}
              onClick={() =>
                removeTag.mutate({
                  tag_type: tag.tag_type,
                  tag_value: tag.tag_value,
                })
              }
              className="ml-0.5 rounded-full hover:text-red-300 disabled:opacity-50"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <form onSubmit={submit} className="mt-3 flex max-w-2xl flex-wrap gap-2">
        <select
          value={tagType}
          onChange={(event) =>
            setTagType(event.target.value as TagInput["tag_type"])
          }
          className="h-8 rounded-md border border-input bg-background/70 px-2 text-xs"
          aria-label="태그 종류"
        >
          {tagTypes.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <Input
          value={tagValue}
          maxLength={120}
          onChange={(event) => setTagValue(event.target.value)}
          placeholder="태그 값"
          className="h-8 min-w-48 flex-1"
          aria-label="태그 값"
        />
        <Button
          type="submit"
          size="sm"
          variant="outline"
          disabled={addTag.isPending || !tagValue.trim()}
        >
          {addTag.isPending ? (
            <LoaderCircle className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="mr-1.5 h-3.5 w-3.5" />
          )}
          추가
        </Button>
      </form>
      {error && <p className="mt-2 text-xs text-red-300">{error.message}</p>}
      <p className="mt-2 text-[10px] text-muted-foreground">
        중복 추가와 이미 삭제된 태그 제거는 idempotent 처리됩니다.
      </p>
    </section>
  );
}

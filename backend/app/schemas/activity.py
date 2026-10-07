"""ساعاتُ العمل كما تقرؤها الإدارة (SPEC §٦٢-ج/٣٧) — **دقائقُ لا ساعاتٌ مقرَّبة**: الشاشةُ تكتبها «4:10» ولا تحسب مالاً."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ActivityDayOut(BaseModel):
    day: date
    minutes: int


class ActivityMonthOut(BaseModel):
    month: date
    minutes: int


class DriverActivityOut(BaseModel):
    #: **مفتاحُ السوق** — مطفأً لا يُحسب شيء، فالأصفارُ «لم يُقَس» لا «لم يعمل»
    enabled: bool
    #: **مجموعةً في الخلفية** — اليوم، وآخرُ سبعةِ أيّام، وآخرُ ثلاثين
    today_minutes: int
    week_minutes: int
    month_minutes: int
    days: list[ActivityDayOut]
    months: list[ActivityMonthOut]

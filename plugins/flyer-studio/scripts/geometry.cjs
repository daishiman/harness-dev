"use strict";

// pad is an inward tolerance, in mm. Shared by input and measured-layout checks.
function overlap(a, b, pad = 0) {
  return (
    a.x + pad < b.x + b.w &&
    a.x + a.w - pad > b.x &&
    a.y + pad < b.y + b.h &&
    a.y + a.h - pad > b.y
  );
}

function inBox(a, b, tolerance = 0.2) {
  return (
    a.x >= b.x - tolerance &&
    a.y >= b.y - tolerance &&
    a.x + a.w <= b.x + b.w + tolerance &&
    a.y + a.h <= b.y + b.h + tolerance
  );
}

// deg is clockwise on the page (y grows downward), as CSS rotate() draws it.
function rotatePoint(point, center, deg) {
  const r = (deg * Math.PI) / 180,
    dx = point.x - center.x,
    dy = point.y - center.y;
  return {
    x: center.x + dx * Math.cos(r) - dy * Math.sin(r),
    y: center.y + dx * Math.sin(r) + dy * Math.cos(r),
  };
}

// Axis-aligned bounds of a box turned about its own center, which is what
// getBoundingClientRect reports for the same CSS transform.
function rotatedBox(box, deg) {
  const r = (deg * Math.PI) / 180,
    cos = Math.abs(Math.cos(r)),
    sin = Math.abs(Math.sin(r)),
    w = box.w * cos + box.h * sin,
    h = box.w * sin + box.h * cos;
  return { x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h };
}

module.exports = { overlap, inBox, rotatePoint, rotatedBox };

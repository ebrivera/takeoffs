"use client";

import { useMemo } from "react";
import type { GeometryPayload, SerializedRoom } from "@/lib/types";

/**
 * Accessible, distinct colors for CSI divisions.
 * Index maps to division order in the breakdown table.
 */
export const DIVISION_COLORS: string[] = [
  "#3b82f6", // blue-500
  "#22c55e", // green-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#06b6d4", // cyan-500
  "#f97316", // orange-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#a855f7", // purple-500
];

/** Get a stable color for a CSI division number. */
export function getDivisionColor(csiDivision: string): string {
  // Map common CSI division numbers to stable indices
  const divNum = parseInt(csiDivision, 10);
  if (isNaN(divNum)) return DIVISION_COLORS[0];
  return DIVISION_COLORS[divNum % DIVISION_COLORS.length];
}

interface DrawingViewerProps {
  geometry: GeometryPayload;
  hoveredDivision: string | null;
  selectedDivision: string | null;
  /** Maps CSI division -> set of ref_types that division uses */
  divisionRefTypes: Map<string, Set<string>>;
}

export default function DrawingViewer({
  geometry,
  hoveredDivision,
  selectedDivision,
  divisionRefTypes,
}: DrawingViewerProps) {
  const activeDivision = selectedDivision ?? hoveredDivision;

  // Determine which ref_types are active
  const activeRefTypes = useMemo(() => {
    if (!activeDivision) return null;
    return divisionRefTypes.get(activeDivision) ?? null;
  }, [activeDivision, divisionRefTypes]);

  const { page_width_pts, page_height_pts } = geometry;

  // SVG viewBox matches PDF point dimensions
  const viewBox = `0 0 ${page_width_pts} ${page_height_pts}`;

  return (
    <div className="relative overflow-hidden rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-950)]">
      {/* Background image — base64 data URL, not optimizable by next/image */}
      {geometry.page_image_base64 && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`data:image/png;base64,${geometry.page_image_base64}`}
          alt="Floor plan"
          className="block w-full"
          style={{ display: "block" }}
          draggable={false}
        />
      )}

      {/* SVG overlay */}
      <svg
        viewBox={viewBox}
        className="absolute inset-0 h-full w-full"
        preserveAspectRatio="xMidYMid meet"
        style={{ pointerEvents: "none" }}
      >
        {/* No Y-flip: PyMuPDF coords are screen-space (Y=0 top), matching the PNG */}
        <g>
          {/* Room polygons */}
          {geometry.rooms.map((room) => (
            <RoomPolygon
              key={room.room_index}
              room={room}
              isActive={activeRefTypes?.has("room_polygon") ?? false}
              isHighlighted={!activeDivision}
              activeDivision={activeDivision}
            />
          ))}

          {/* Wall segments */}
          {geometry.wall_segments.map((seg, i) => {
            const wallActive = activeRefTypes?.has("wall_segment") ?? false;
            const dimmed = activeDivision && !wallActive;
            return (
              <line
                key={i}
                x1={seg.start[0]}
                y1={seg.start[1]}
                x2={seg.end[0]}
                y2={seg.end[1]}
                stroke={
                  wallActive && activeDivision
                    ? getDivisionColor(activeDivision)
                    : "rgba(148,163,184,0.4)"
                }
                strokeWidth={wallActive && activeDivision ? 2.5 : 1.5}
                strokeOpacity={dimmed ? 0.05 : wallActive && activeDivision ? 0.8 : 0.15}
                className="transition-all duration-150"
              />
            );
          })}

          {/* Outer boundary */}
          {geometry.outer_boundary && (
            <polygon
              points={geometry.outer_boundary.map((pt) => pt.join(",")).join(" ")}
              fill="none"
              stroke={
                activeRefTypes?.has("building_footprint") && activeDivision
                  ? getDivisionColor(activeDivision)
                  : "rgba(148,163,184,0.3)"
              }
              strokeWidth={
                activeRefTypes?.has("building_footprint") && activeDivision ? 3 : 1.5
              }
              strokeOpacity={
                activeDivision && !activeRefTypes?.has("building_footprint")
                  ? 0.05
                  : activeRefTypes?.has("building_footprint") && activeDivision
                    ? 0.9
                    : 0.2
              }
              strokeDasharray={
                activeRefTypes?.has("building_footprint") && activeDivision
                  ? "none"
                  : "6 4"
              }
              className="transition-all duration-150"
            />
          )}

          {/* Room labels — same coord space as polygons */}
          {geometry.rooms.map((room) => {
            if (!room.label || !room.centroid) return null;
            const dimmed = activeDivision && !activeRefTypes?.has("room_polygon");
            return (
              <text
                key={`label-${room.room_index}`}
                x={room.centroid[0]}
                y={room.centroid[1]}
                textAnchor="middle"
                dominantBaseline="central"
                fill="white"
                fontSize={10}
                fontWeight={500}
                opacity={dimmed ? 0.1 : 0.7}
                className="pointer-events-none select-none transition-opacity duration-150"
                style={{ textShadow: "0 1px 3px rgba(0,0,0,0.8)" }}
              >
                {room.label}
              </text>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

function RoomPolygon({
  room,
  isActive,
  isHighlighted,
  activeDivision,
}: {
  room: SerializedRoom;
  isActive: boolean;
  isHighlighted: boolean;
  activeDivision: string | null;
}) {
  const points = room.polygon_pts.map((pt) => pt.join(",")).join(" ");

  // Color based on active division
  const fillColor =
    isActive && activeDivision
      ? getDivisionColor(activeDivision)
      : "rgba(59,130,246,0.5)";

  const fillOpacity = activeDivision
    ? isActive
      ? 0.35
      : 0.02
    : isHighlighted
      ? 0.08
      : 0.08;

  const strokeOpacity = activeDivision
    ? isActive
      ? 0.7
      : 0.03
    : 0.15;

  return (
    <polygon
      points={points}
      fill={fillColor}
      fillOpacity={fillOpacity}
      stroke={
        isActive && activeDivision
          ? getDivisionColor(activeDivision)
          : "rgba(148,163,184,0.5)"
      }
      strokeWidth={isActive && activeDivision ? 2 : 1}
      strokeOpacity={strokeOpacity}
      className="transition-all duration-150"
    />
  );
}

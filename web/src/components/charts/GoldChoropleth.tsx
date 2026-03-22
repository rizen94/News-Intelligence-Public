/**
 * D3 choropleth world map — event density by country for gold commodity view.
 * Fetches TopoJSON from CDN, colors countries by event count, supports click and tooltip.
 */
import React, { useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';
import * as topojson from 'topojson-client';
import { Box, Typography } from '@mui/material';
import Logger from '../../utils/logger';

const WORLD_TOPOLOGY_URL =
  'https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json';

/** Map API geographic_scope / by_region keys to TopoJSON country properties.name */
const REGION_TO_COUNTRY_NAME: Record<string, string> = {
  USA: 'United States of America',
  US: 'United States of America',
  'United States': 'United States of America',
  California: 'United States of America',
  India: 'India',
  UK: 'United Kingdom',
  'United Kingdom': 'United Kingdom',
  China: 'China',
  Russia: 'Russian Federation',
  Brazil: 'Brazil',
  Germany: 'Germany',
  France: 'France',
  Japan: 'Japan',
  Australia: 'Australia',
  Canada: 'Canada',
  'South Africa': 'South Africa',
  Mexico: 'Mexico',
  Iran: 'Iran',
  Israel: 'Israel',
  UAE: 'United Arab Emirates',
  'Saudi Arabia': 'Saudi Arabia',
  Turkey: 'Turkey',
  Indonesia: 'Indonesia',
  Global: 'United States of America',
};

export interface GeoEvent {
  id: number;
  event_name: string | null;
  event_type: string | null;
  geographic_scope: string | null;
  start_date: string | null;
  end_date: string | null;
  domain_keys?: string[];
  /** finance_native | cross_domain — from commodity geo-events API */
  display_source?: string;
}

/** GeoJSON FeatureCollection from commodity map_overlays API */
export interface MapOverlayFeatureCollection {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    properties?: Record<string, unknown>;
    geometry: {
      type: string;
      coordinates: number[] | number[][] | number[][][];
    };
  }>;
  disclaimer?: string;
}

export interface GoldChoroplethProps {
  events: GeoEvent[];
  byRegion: Record<string, number[]>;
  onCountryClick?: (countryName: string, eventIds: number[]) => void;
  width?: number;
  height?: number;
  /** Static reference chokepoints / corridors (not live AIS) */
  mapOverlays?: MapOverlayFeatureCollection | null;
  showOverlays?: boolean;
}

function buildCountByCountry(
  byRegion: Record<string, number[]>
): Record<string, number> {
  const countByCountry: Record<string, number> = {};
  for (const [region, eventIds] of Object.entries(byRegion)) {
    const name = REGION_TO_COUNTRY_NAME[region] ?? region;
    countByCountry[name] =
      (countByCountry[name] ?? 0) + (eventIds?.length ?? 0);
  }
  return countByCountry;
}

export default function GoldChoropleth({
  events,
  byRegion,
  onCountryClick,
  width = 960,
  height = 500,
  mapOverlays = null,
  showOverlays = true,
}: GoldChoroplethProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  const draw = useCallback(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const countByCountry = buildCountByCountry(byRegion);
    const maxCount = Math.max(1, ...Object.values(countByCountry));

    const colorScale = d3
      .scaleSequential(d3.interpolateBlues)
      .domain([0, maxCount]);

    const projection = d3
      .geoMercator()
      .scale(140)
      .translate([width / 2, height / 2]);
    const pathGenerator = d3.geoPath().projection(projection);

    fetch(WORLD_TOPOLOGY_URL)
      .then(r => r.json())
      .then((topology: unknown) => {
        const t = topology as { objects: { countries: unknown } };
        const raw = topojson.feature(t as never, t.objects.countries as never);
        const geojson = raw as {
          features?: Array<{
            properties?: { name?: string };
            geometry?: unknown;
          }>;
        };
        if (!geojson?.features) return;

        const g = svg.append('g');

        g.selectAll('path')
          .data(geojson.features)
          .join('path')
          .attr(
            'd',
            pathGenerator as (d: (typeof geojson.features)[0]) => string
          )
          .attr('fill', d => {
            const name = (d.properties as { name?: string })?.name ?? '';
            const count = countByCountry[name] ?? 0;
            return colorScale(count);
          })
          .attr('stroke', '#333')
          .attr('stroke-width', 0.5)
          .attr('title', d => {
            const name = (d.properties as { name?: string })?.name ?? '';
            const count = countByCountry[name] ?? 0;
            return `${name}: ${count} event(s)`;
          })
          .style('cursor', 'pointer')
          .on('mouseover', function () {
            d3.select(this).attr('stroke-width', 1.5).attr('stroke', '#111');
          })
          .on('mouseout', function () {
            d3.select(this).attr('stroke-width', 0.5).attr('stroke', '#333');
          })
          .on('click', (event, d) => {
            const name = (d.properties as { name?: string })?.name ?? '';
            const eventIds: number[] = [];
            for (const [region, ids] of Object.entries(byRegion)) {
              if (REGION_TO_COUNTRY_NAME[region] === name || region === name)
                eventIds.push(...(ids ?? []));
            }
            onCountryClick?.(name, eventIds);
          });

        if (
          showOverlays &&
          mapOverlays?.features &&
          mapOverlays.features.length > 0
        ) {
          const overlayG = svg.append('g').attr('class', 'commodity-map-overlays');
          for (const f of mapOverlays.features) {
            const geom = f.geometry;
            if (!geom || !geom.type) continue;
            if (geom.type === 'LineString') {
              const lineGeom = {
                type: 'LineString' as const,
                coordinates: geom.coordinates as [number, number][],
              };
              const dPath = pathGenerator(lineGeom as never);
              if (dPath) {
                overlayG
                  .append('path')
                  .attr('d', dPath)
                  .attr('fill', 'none')
                  .attr('stroke', '#c62828')
                  .attr('stroke-width', 1.25)
                  .attr('stroke-dasharray', '5 3')
                  .attr('opacity', 0.85)
                  .attr('pointer-events', 'none');
              }
            } else if (geom.type === 'Point') {
              const coords = geom.coordinates as number[];
              if (coords.length >= 2) {
                const p = projection([coords[0], coords[1]]);
                if (p) {
                  overlayG
                    .append('circle')
                    .attr('cx', p[0])
                    .attr('cy', p[1])
                    .attr('r', 5)
                    .attr('fill', '#c62828')
                    .attr('stroke', '#fff')
                    .attr('stroke-width', 0.75)
                    .attr('opacity', 0.9)
                    .attr('pointer-events', 'none');
                }
              }
            }
          }
        }
      })
      .catch(err => {
        Logger.error('GoldChoropleth fetch topology failed', err as Error);
      });
  }, [byRegion, width, height, onCountryClick, mapOverlays, showOverlays]);

  useEffect(() => {
    draw();
  }, [draw]);

  const countByCountry = buildCountByCountry(byRegion);
  const maxCount = Math.max(0, ...Object.values(countByCountry));
  const hasData = maxCount > 0;

  return (
    <Box sx={{ width: '100%', overflow: 'hidden' }}>
      <Typography
        variant='caption'
        color='text.secondary'
        sx={{ display: 'block', mb: 0.5 }}
      >
        {hasData
          ? 'Darker shading = more events in that country — click a country to filter the timeline below.'
          : 'No event counts mapped to countries yet (events need a geographic scope the map understands). The outline is a preview.'}
      </Typography>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        style={{ maxWidth: '100%', height: 'auto' }}
      />
      {hasData && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
          <Typography variant='caption' color='text.secondary'>
            Event count:
          </Typography>
          <Box
            sx={{
              width: 80,
              height: 8,
              borderRadius: 1,
              background: 'linear-gradient(to right, #deebf7 0%, #3182bd 100%)',
            }}
          />
          <Typography variant='caption' color='text.secondary'>
            0 — {maxCount}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

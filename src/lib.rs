use pyo3::prelude::*;
use std::collections::HashSet;

#[inline]
fn distance(p0: (f32, f32), p1: (f32, f32)) -> f32 {
    ((p0.0 - p1.0).powi(2) + (p0.1 - p1.1).powi(2)).sqrt()
}

#[inline]
fn lerp(p0: (f32, f32), p1: (f32, f32), t: f32) -> (f32, f32) {
    (p0.0 * (1.0 - t) + p1.0 * t, p0.1 * (1.0 - t) + p1.1 * t)
}

#[inline]
fn eqline(p0: (f32, f32), p1: (f32, f32)) -> (f32, f32, f32) {
    (p1.1 - p0.1, p0.0 - p1.0, p1.0 * p0.1 - p1.1 * p0.0)
}

#[inline]
fn online(p0: (f32, f32), p1: (f32, f32), p2: (f32, f32)) -> f32 {
    let ep = 1.0;
    let d0 = distance(p1, p2);
    let d1 = distance(p0, p1);
    let d2 = distance(p0, p2);
    let eps = 1e-6;
    if (d0 + d1 - d2).abs() < ep {
        d1
    } else if (d0 + d2 - d1).abs() < ep {
        d2
    } else if (d1 + d2 - d0).abs() < eps {
        0.0
    } else {
        0.0
    }
}

#[inline]
fn intersect(seg0: &[(f32, f32)], seg1: &[(f32, f32)]) -> Option<((f32, f32), (f32, f32))> {
    let (a, b, c) = eqline(seg0[0], seg0[1]);
    let (d, e, f) = eqline(seg1[0], seg1[1]);
    let det = d * b - a * e;
    if det == 0.0 {
        return None;
    }
    let y = (f * a - c * d) / det;
    let x = if a != 0.0 { (-b * y - c) / a } else { (-e * y - f) / d };
    let od0 = online((x, y), seg0[0], seg0[1]);
    let od1 = online((x, y), seg1[0], seg1[1]);
    Some(((x, y), (od0, od1)))
}

#[inline]
fn vecang(seg0: &[(f32, f32)], seg1: &[(f32, f32)]) -> f32 {
    let ux = seg0[1].0 - seg0[0].0;
    let uy = seg0[1].1 - seg0[0].1;
    let vx = seg1[1].0 - seg1[0].0;
    let vy = seg1[1].1 - seg1[0].1;
    let dot = ux * vx + uy * vy;
    let norm_u = (ux * ux + uy * uy).sqrt();
    let norm_v = (vx * vx + vy * vy).sqrt();
    if norm_u == 0.0 || norm_v == 0.0 {
        return std::f32::consts::FRAC_PI_2;
    }
    let angcos = (dot / (norm_u * norm_v)).max(-1.0).min(1.0);
    angcos.acos()
}

#[inline]
fn pt2seg_dist_point(px: f32, py: f32, x1: f32, y1: f32, x2: f32, y2: f32) -> (f32, f32, f32) {
    let (a, b, c) = eqline((x1, y1), (x2, y2));
    let a2b2 = (a * a + b * b).sqrt();
    if a2b2 == 0.0 {
        return (distance((px, py), (x1, y1)), 0.0, 0.0);
    }
    let d = (a * px + b * py + c).abs() / a2b2;
    let bx = (b * (b * px - a * py) - a * c) / (a * a + b * b);
    let by = (a * (-b * px + a * py) - b * c) / (a * a + b * b);
    let b_val = online((bx, by), (x1, y1), (x2, y2));
    (d, bx, b_val)
}

type Segment = Vec<(f32, f32)>;

#[pyfunction]
pub fn scan_rast(mtx: Vec<Vec<u8>>, strw: f32, ngradient: i32) -> PyResult<Vec<Vec<Vec<f32>>>> {
    let h = mtx.len();
    let w = if h > 0 { mtx[0].len() } else { 0 };
    
    let mut segs: Vec<Segment> = Vec::new();
    
    let steptypes: Vec<(i32, i32)> = match ngradient {
        1 => vec![(0, 1), (1, 0), (1, 1), (-1, 1)],
        2 => vec![(0, 1), (1, 0), (1, 1), (-1, 1), (1, 2), (2, 1), (-1, 2), (-2, 1)],
        3 => vec![(0, 1), (1, 0), (1, 1), (-1, 1), (1, 2), (2, 1), (-1, 2), (-2, 1), (1, 3), (3, 1), (-1, 3), (-3, 1)],
        _ => vec![(0, 1), (1, 0), (1, 1), (-1, 1), (1, 2), (2, 1), (-1, 2), (-2, 1), (1, 3), (3, 1), (-1, 3), (-3, 1), (1, 4), (4, 1), (-1, 4), (-4, 1)],
    };
    
    for &(dx, dy) in &steptypes {
        if dx == 0 {
            for y in 0..h as i32 {
                let mut in_segment = false;
                let mut start_x = 0;
                for x in 0..w as i32 {
                    let val = mtx[y as usize][x as usize];
                    if val == 1 && !in_segment {
                        in_segment = true;
                        start_x = x;
                    } else if val == 0 && in_segment {
                        in_segment = false;
                        if x - start_x > 1 {
                            segs.push(vec![(start_x as f32, y as f32), (x as f32, y as f32)]);
                        }
                    }
                }
                if in_segment {
                    segs.push(vec![(start_x as f32, y as f32), (w as f32, y as f32)]);
                }
            }
        } else if dy == 0 {
            for x in 0..w as i32 {
                let mut in_segment = false;
                let mut start_y = 0;
                for y in 0..h as i32 {
                    let val = mtx[y as usize][x as usize];
                    if val == 1 && !in_segment {
                        in_segment = true;
                        start_y = y;
                    } else if val == 0 && in_segment {
                        in_segment = false;
                        if y - start_y > 1 {
                            segs.push(vec![(x as f32, start_y as f32), (x as f32, y as f32)]);
                        }
                    }
                }
                if in_segment {
                    segs.push(vec![(x as f32, start_y as f32), (x as f32, h as f32)]);
                }
            }
        } else {
            let step_x = dx;
            let step_y = dy;
            
            if step_x > 0 && step_y > 0 {
                for start_y in 0..h as i32 {
                    let mut x: i32 = 0;
                    let mut y = start_y;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x < w as i32 && y < h as i32 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
                for start_x in 1..w as i32 {
                    let mut x = start_x;
                    let mut y: i32 = 0;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x < w as i32 && y < h as i32 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
            } else if step_x < 0 && step_y > 0 {
                for start_y in 0..h as i32 {
                    let mut x = w as i32 - 1;
                    let mut y = start_y;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x >= 0 && y < h as i32 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
                for start_x in 0..w as i32 - 1 {
                    let mut x = start_x;
                    let mut y: i32 = 0;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x >= 0 && y < h as i32 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
            } else if step_x > 0 && step_y < 0 {
                for start_y in 0..h as i32 {
                    let mut x: i32 = 0;
                    let mut y = start_y;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x < w as i32 && y >= 0 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
                for start_x in 1..w as i32 {
                    let mut x = start_x;
                    let mut y = h as i32 - 1;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x < w as i32 && y >= 0 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
            } else {
                for start_y in 0..h as i32 {
                    let mut x = w as i32 - 1;
                    let mut y = start_y;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x >= 0 && y >= 0 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
                for start_x in 0..w as i32 - 1 {
                    let mut x = start_x;
                    let mut y = h as i32 - 1;
                    let mut in_segment = false;
                    let mut start_pos = (0, 0);
                    while x >= 0 && y >= 0 {
                        let val = mtx[y as usize][x as usize];
                        if val == 1 && !in_segment {
                            in_segment = true;
                            start_pos = (x, y);
                        } else if val == 0 && in_segment {
                            in_segment = false;
                            segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                        }
                        x += step_x;
                        y += step_y;
                    }
                    if in_segment {
                        segs.push(vec![(start_pos.0 as f32, start_pos.1 as f32), (x as f32, y as f32)]);
                    }
                }
            }
        }
    }
    
    segs.retain(|seg| seg.len() >= 2 && distance(seg[0], seg[1]) > strw * 0.5);
    
    let mut ssegs: Vec<Segment> = Vec::new();
    if !segs.is_empty() {
        let mut gp_means0: Vec<Vec<f32>> = Vec::new();
        let mut gp_means1: Vec<Vec<f32>> = Vec::new();
        let mut gp_counts: Vec<i32> = Vec::new();
        let mut gp_maxs: Vec<(Segment, f32)> = Vec::new();
        
        for seg in &segs {
            let x0 = seg[0].0;
            let y0 = seg[0].1;
            let x1 = seg[1].0;
            let y1 = seg[1].1;
            let d = distance((x0, y0), (x1, y1));
            let mut grouped = false;
            
            for j in 0..gp_means0.len() {
                let dx0 = (x0 - gp_means0[j][0]).abs();
                let dy0 = (y0 - gp_means0[j][1]).abs();
                let dx1 = (x1 - gp_means1[j][0]).abs();
                let dy1 = (y1 - gp_means1[j][1]).abs();
                if dx0 < strw && dy0 < strw && dx1 < strw && dy1 < strw {
                    let cnt = gp_counts[j] as f32;
                    gp_counts[j] += 1;
                    gp_means0[j][0] = (gp_means0[j][0] * cnt + x0) / (cnt + 1.0);
                    gp_means0[j][1] = (gp_means0[j][1] * cnt + y0) / (cnt + 1.0);
                    gp_means1[j][0] = (gp_means1[j][0] * cnt + x1) / (cnt + 1.0);
                    gp_means1[j][1] = (gp_means1[j][1] * cnt + y1) / (cnt + 1.0);
                    if d > gp_maxs[j].1 {
                        gp_maxs[j] = (seg.clone(), d);
                    }
                    grouped = true;
                    break;
                }
            }
            
            if !grouped {
                gp_means0.push(vec![x0, y0]);
                gp_means1.push(vec![x1, y1]);
                gp_counts.push(1);
                gp_maxs.push((seg.clone(), d));
            }
        }
        
        ssegs = gp_maxs.into_iter().map(|(seg, _)| seg).collect();
    }
    
    let mut to_remove: HashSet<usize> = HashSet::new();
    let n = ssegs.len();
    for i in 0..n {
        if to_remove.contains(&i) {
            continue;
        }
        let seg_i = &ssegs[i];
        let len_i = distance(seg_i[0], seg_i[1]);
        for j in 0..n {
            if i == j || to_remove.contains(&j) {
                continue;
            }
            let seg_j = &ssegs[j];
            let len_j = distance(seg_j[0], seg_j[1]);
            if len_i < len_j {
                let (d0, _, b0) = pt2seg_dist_point(seg_i[0].0, seg_i[0].1, seg_j[0].0, seg_j[0].1, seg_j[1].0, seg_j[1].1);
                let (d1, _, b1) = pt2seg_dist_point(seg_i[1].0, seg_i[1].1, seg_j[0].0, seg_j[0].1, seg_j[1].0, seg_j[1].1);
                if d0 < strw && d1 < strw && b0 < strw && b1 < strw {
                    to_remove.insert(i);
                    break;
                }
            }
        }
    }
    
    ssegs = ssegs.into_iter().enumerate()
        .filter(|(i, _)| !to_remove.contains(i))
        .map(|(_, seg)| seg)
        .collect();
    
    to_remove.clear();
    let n = ssegs.len();
    for i in 0..n {
        if to_remove.contains(&i) {
            continue;
        }
        let seg_i = &ssegs[i];
        for j in 0..n {
            if i == j || to_remove.contains(&j) {
                continue;
            }
            let seg_j = &ssegs[j];
            let d0 = distance(seg_i[0], seg_j[0]);
            let d1 = distance(seg_i[1], seg_j[1]);
            if d0 < strw && d1 < strw {
                to_remove.insert(i);
                break;
            }
        }
    }
    
    ssegs = ssegs.into_iter().enumerate()
        .filter(|(i, _)| !to_remove.contains(i))
        .map(|(_, seg)| seg)
        .collect();
    
    to_remove.clear();
    let n = ssegs.len();
    for i in 0..n {
        if to_remove.contains(&i) {
            continue;
        }
        let seg_i = &ssegs[i];
        let seg0 = if seg_i.len() >= 2 { &seg_i[seg_i.len()-2..] } else { seg_i };
        for j in 0..n {
            if i == j || to_remove.contains(&j) {
                continue;
            }
            let seg_j = &ssegs[j];
            let seg1 = &seg_j[..2.min(seg_j.len())];
            
            let ir = intersect(seg0, seg1);
            let has_intercept = ir.is_some();
            let (od0, od1) = if let Some((_, (o0, o1))) = ir {
                (o0, o1)
            } else {
                (0.0, 0.0)
            };
            
            let ang = vecang(seg0, seg1);
            let p_i_last = seg_i.last().unwrap();
            let p_j_first = seg_j.first().unwrap();
            let d = distance(*p_i_last, *p_j_first);
            
            if d < strw || (has_intercept && od0 == 0.0 && od1 == 0.0) || ang < std::f32::consts::FRAC_PI_4 {
                let (d0, _, b0) = pt2seg_dist_point(p_i_last.0, p_i_last.1, seg1[0].0, seg1[0].1, seg1[1].0, seg1[1].1);
                let (d1, _, b1) = pt2seg_dist_point(seg_j[0].0, seg_j[0].1, seg0[0].0, seg0[0].1, seg0[1].0, seg0[1].1);
                if d0 < strw && d1 < strw && b0 < 1.0 && b1 < 1.0 {
                    let mid = lerp(*p_i_last, seg_j[0], 0.5);
                    let mut new_seg = seg_i[..seg_i.len()-1].to_vec();
                    new_seg.push(mid);
                    new_seg.extend_from_slice(&seg_j[1..]);
                    ssegs[j] = new_seg;
                    to_remove.insert(i);
                    break;
                }
            }
        }
    }
    
    ssegs = ssegs.into_iter().enumerate()
        .filter(|(i, _)| !to_remove.contains(i))
        .map(|(_, seg)| seg)
        .collect();
    
    let result: Vec<Vec<Vec<f32>>> = ssegs
        .iter()
        .map(|seg| {
            seg.iter()
                .map(|(x, y)| vec![*x, *y])
                .collect()
        })
        .collect();
    
    Ok(result)
}

#[pymodule]
fn char2stroke_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(scan_rast, m)?)?;
    Ok(())
}

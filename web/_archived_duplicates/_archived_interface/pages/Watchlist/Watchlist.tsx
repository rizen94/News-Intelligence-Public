import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Button,
  CircularProgress,
  Alert,
  Badge,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tooltip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import NotificationsIcon from '@mui/icons-material/Notifications';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import TimelineIcon from '@mui/icons-material/Timeline';
import WarningIcon from '@mui/icons-material/Warning';
import LinkIcon from '@mui/icons-material/Link';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { useDomain } from '../../contexts/DomainContext';
import apiService from '../../services/apiService';

const STATUS_COLORS: Record<string, 'success' | 'warning' | 'info' | 'error' | 'default'> = {
  active: 'success',
  watching: 'info',
  dormant: 'warning',
  concluded: 'default',
  archived: 'default',
};

interface TabPanelProps {
  children: React.ReactNode;
  value: number;
  index: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <Box hidden={value !== index} sx={{ pt: 2 }}>
    {value === index && children}
  </Box>
);

const Watchlist: React.FC = () => {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [activityFeed, setActivityFeed] = useState<any[]>([]);
  const [dormantStories, setDormantStories] = useState<any[]>([]);
  const [coverageGaps, setCoverageGaps] = useState<any[]>([]);
  const [crossDomain, setCrossDomain] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const unreadCount = alerts.filter(a => !a.is_read).length;

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [wl, al, af, ds, cg, cd] = await Promise.all([
        apiService.getWatchlist(),
        apiService.getWatchlistAlerts(false, 50),
        apiService.getActivityFeed(30),
        apiService.getDormantAlerts(30),
        apiService.getCoverageGaps(7),
        apiService.getCrossDomainConnections(),
      ]);
      setWatchlist(wl?.data || []);
      setAlerts(al?.data || []);
      setActivityFeed(af?.data || []);
      setDormantStories(ds?.data || []);
      setCoverageGaps(cg?.data || []);
      setCrossDomain(cd?.data || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleRemove = async (storylineId: number) => {
    await apiService.removeFromWatchlist(storylineId);
    loadAll();
  };

  const handleMarkAllRead = async () => {
    await apiService.markAllAlertsRead();
    loadAll();
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Watchlist & Monitoring
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Watched (${watchlist.length})`} />
        <Tab
          label={
            <Badge badgeContent={unreadCount} color="error">
              Alerts
            </Badge>
          }
        />
        <Tab label="Activity Feed" />
        <Tab label="Monitoring" />
      </Tabs>

      {/* Tab 0: Watched Storylines */}
      <TabPanel value={tab} index={0}>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Storyline</TableCell>
                <TableCell>Label</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="center">Events</TableCell>
                <TableCell>Last Event</TableCell>
                <TableCell align="center">Unread</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {watchlist.map(w => (
                <TableRow key={w.watchlist_id} hover>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                      onClick={() => navigate(`/${domain}/storylines/${w.storyline_id}/timeline`)}
                    >
                      {w.storyline_title}
                    </Typography>
                  </TableCell>
                  <TableCell>{w.user_label || '—'}</TableCell>
                  <TableCell>
                    <Chip label={w.storyline_status} size="small" color={STATUS_COLORS[w.storyline_status] || 'default'} />
                  </TableCell>
                  <TableCell align="center">{w.total_events}</TableCell>
                  <TableCell>
                    {w.last_event_at ? new Date(w.last_event_at).toLocaleDateString() : '—'}
                  </TableCell>
                  <TableCell align="center">
                    {w.unread_alerts > 0 ? (
                      <Badge badgeContent={w.unread_alerts} color="error">
                        <NotificationsIcon fontSize="small" />
                      </Badge>
                    ) : '—'}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View timeline">
                      <IconButton size="small" onClick={() => navigate(`/${domain}/storylines/${w.storyline_id}/timeline`)}>
                        <TimelineIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Remove from watchlist">
                      <IconButton size="small" color="error" onClick={() => handleRemove(w.storyline_id)}>
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {watchlist.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No watched storylines. Add storylines from the Storylines page.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Tab 1: Alerts */}
      <TabPanel value={tab} index={1}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<DoneAllIcon />} onClick={handleMarkAllRead} disabled={unreadCount === 0}>
            Mark all read
          </Button>
        </Box>
        <List>
          {alerts.map(a => (
            <React.Fragment key={a.id}>
              <ListItem
                sx={{
                  bgcolor: a.is_read ? 'transparent' : 'action.hover',
                  cursor: 'pointer',
                }}
                onClick={async () => {
                  if (!a.is_read) await apiService.markAlertRead(a.id);
                  if (a.storyline_id) navigate(`/${domain}/storylines/${a.storyline_id}/timeline`);
                }}
              >
                <ListItemIcon>
                  <NotificationsIcon color={a.is_read ? 'disabled' : 'primary'} />
                </ListItemIcon>
                <ListItemText
                  primary={a.title}
                  secondary={
                    <>
                      {a.body && <Typography variant="body2" color="text.secondary">{a.body}</Typography>}
                      <Typography variant="caption" color="text.disabled">
                        {a.alert_type.replace('_', ' ')} · {a.storyline_title} · {new Date(a.created_at).toLocaleString()}
                      </Typography>
                    </>
                  }
                />
                <Chip label={a.alert_type.replace('_', ' ')} size="small" variant="outlined" />
              </ListItem>
              <Divider />
            </React.Fragment>
          ))}
          {alerts.length === 0 && (
            <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
              No alerts yet.
            </Typography>
          )}
        </List>
      </TabPanel>

      {/* Tab 2: Activity Feed */}
      <TabPanel value={tab} index={2}>
        <List>
          {activityFeed.map((item, i) => (
            <React.Fragment key={i}>
              <ListItem
                sx={{ cursor: 'pointer' }}
                onClick={() => {
                  if (item.storyline_id) navigate(`/${domain}/storylines/${item.storyline_id}/timeline`);
                }}
              >
                <ListItemIcon>
                  <VisibilityIcon color="action" />
                </ListItemIcon>
                <ListItemText
                  primary={item.event_title}
                  secondary={
                    <>
                      <Chip label={item.event_type?.replace('_', ' ')} size="small" sx={{ mr: 1 }} />
                      {item.storyline_title && <Typography variant="caption" color="text.secondary">in {item.storyline_title}</Typography>}
                      {item.event_date && <Typography variant="caption" display="block" color="text.disabled">{item.event_date}</Typography>}
                    </>
                  }
                />
                {item.source_count > 1 && <Chip label={`${item.source_count} sources`} size="small" color="info" variant="outlined" />}
              </ListItem>
              <Divider />
            </React.Fragment>
          ))}
          {activityFeed.length === 0 && (
            <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
              No recent activity.
            </Typography>
          )}
        </List>
      </TabPanel>

      {/* Tab 3: Monitoring Dashboard */}
      <TabPanel value={tab} index={3}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          {/* Dormant Stories */}
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <TrendingDownIcon color="warning" />
                <Typography variant="h6">Dormant Watched Stories</Typography>
              </Box>
              {dormantStories.length === 0 ? (
                <Typography color="text.secondary">All watched stories are active.</Typography>
              ) : (
                <List dense>
                  {dormantStories.map(ds => (
                    <ListItem key={ds.storyline_id} sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/${domain}/storylines/${ds.storyline_id}/timeline`)}>
                      <ListItemText
                        primary={ds.title}
                        secondary={`Dormant since ${ds.dormant_since ? new Date(ds.dormant_since).toLocaleDateString() : 'unknown'} · ${ds.total_events} events`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>

          {/* Coverage Gaps */}
          <Card variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <WarningIcon color="error" />
                <Typography variant="h6">Coverage Gaps</Typography>
              </Box>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                Active stories with no new sources in 7+ days
              </Typography>
              {coverageGaps.length === 0 ? (
                <Typography color="text.secondary">No coverage gaps detected.</Typography>
              ) : (
                <List dense>
                  {coverageGaps.map(cg => (
                    <ListItem key={cg.storyline_id} sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/${domain}/storylines/${cg.storyline_id}`)}>
                      <ListItemText
                        primary={cg.title}
                        secondary={`Last event: ${cg.last_event_at ? new Date(cg.last_event_at).toLocaleDateString() : 'never'}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>

          {/* Cross-Domain Connections */}
          <Card variant="outlined" sx={{ gridColumn: { md: '1 / -1' } }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <LinkIcon color="primary" />
                <Typography variant="h6">Cross-Domain Connections</Typography>
              </Box>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                Storylines sharing core entities across different topics
              </Typography>
              {crossDomain.length === 0 ? (
                <Typography color="text.secondary">No cross-domain connections found yet.</Typography>
              ) : (
                <List dense>
                  {crossDomain.map((cd, i) => (
                    <ListItem key={i}>
                      <ListItemIcon><LinkIcon /></ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                            <Chip label={cd.storyline_a.title} size="small" variant="outlined"
                              onClick={() => navigate(`/${domain}/storylines/${cd.storyline_a.id}`)} />
                            <Typography variant="caption">↔</Typography>
                            <Chip label={cd.storyline_b.title} size="small" variant="outlined"
                              onClick={() => navigate(`/${domain}/storylines/${cd.storyline_b.id}`)} />
                          </Box>
                        }
                        secondary={`Shared entities: ${(cd.shared_entities || []).join(', ')}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Box>
      </TabPanel>
    </Box>
  );
};

export default Watchlist;

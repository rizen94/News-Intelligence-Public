import React from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardActions,
  CardProps,
  useTheme,
  useMediaQuery,
  Box,
  Typography,
  IconButton,
  Chip,
  Skeleton
} from '@mui/material';
import { MoreVert as MoreVertIcon } from '@mui/icons-material';

interface ResponsiveCardProps extends CardProps {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  loading?: boolean;
  elevation?: number;
  variant?: 'elevation' | 'outlined';
  headerAction?: React.ReactNode;
  tags?: string[];
  status?: 'success' | 'warning' | 'error' | 'info';
  compact?: boolean;
}

const ResponsiveCard: React.FC<ResponsiveCardProps> = ({
  title,
  subtitle,
  action,
  loading = false,
  elevation = 1,
  variant = 'elevation',
  headerAction,
  tags = [],
  status,
  compact = false,
  children,
  sx = {},
  ...props
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'success': return theme.palette.success.main;
      case 'warning': return theme.palette.warning.main;
      case 'error': return theme.palette.error.main;
      case 'info': return theme.palette.info.main;
      default: return theme.palette.primary.main;
    }
  };

  if (loading) {
    return (
      <Card
        elevation={elevation}
        variant={variant}
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          ...sx
        }}
        {...props}
      >
        <CardHeader
          title={<Skeleton variant="text" width="60%" />}
          subheader={<Skeleton variant="text" width="40%" />}
          action={<Skeleton variant="circular" width={24} height={24} />}
        />
        <CardContent sx={{ flexGrow: 1 }}>
          <Skeleton variant="text" width="100%" />
          <Skeleton variant="text" width="80%" />
          <Skeleton variant="text" width="60%" />
        </CardContent>
        <CardActions>
          <Skeleton variant="rectangular" width="100%" height={36} />
        </CardActions>
      </Card>
    );
  }

  return (
    <Card
      elevation={elevation}
      variant={variant}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          elevation: elevation + 2,
          transform: 'translateY(-2px)',
        },
        ...(status && {
          borderLeft: `4px solid ${getStatusColor(status)}`,
        }),
        ...sx
      }}
      {...props}
    >
      {(title || subtitle || headerAction) && (
        <CardHeader
          title={
            <Typography
              variant={isMobile ? 'subtitle1' : 'h6'}
              component="div"
              sx={{
                fontWeight: 600,
                lineHeight: 1.2,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {title}
            </Typography>
          }
          subheader={
            subtitle && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{
                  display: '-webkit-box',
                  WebkitLineClamp: 1,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {subtitle}
              </Typography>
            )
          }
          action={
            headerAction || (
              <IconButton size="small">
                <MoreVertIcon />
              </IconButton>
            )
          }
          sx={{
            pb: compact ? 1 : 2,
            '& .MuiCardHeader-content': {
              minWidth: 0,
            },
          }}
        />
      )}

      <CardContent
        sx={{
          flexGrow: 1,
          py: compact ? 1 : 2,
          '&:last-child': {
            pb: compact ? 1 : 2,
          },
        }}
      >
        {tags.length > 0 && (
          <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {tags.slice(0, isMobile ? 2 : isTablet ? 3 : 4).map((tag, index) => (
              <Chip
                key={index}
                label={tag}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.75rem' }}
              />
            ))}
            {tags.length > (isMobile ? 2 : isTablet ? 3 : 4) && (
              <Chip
                label={`+${tags.length - (isMobile ? 2 : isTablet ? 3 : 4)}`}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.75rem' }}
              />
            )}
          </Box>
        )}
        {children}
      </CardContent>

      {action && (
        <CardActions
          sx={{
            pt: 0,
            px: compact ? 1 : 2,
            pb: compact ? 1 : 2,
          }}
        >
          {action}
        </CardActions>
      )}
    </Card>
  );
};

export default ResponsiveCard;


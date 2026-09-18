from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrReadOnly
from apps.products.models import Category, Product
from apps.products.serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductWriteSerializer,
)


class DualLookupMixin:
    """
    Allows resolving objects either by numeric ID (primary key) or slug string.
    """

    lookup_field = "pk"
    lookup_url_kwarg = "pk"
    lookup_value_regex = r"[^/.]+"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)

        if lookup_value is None:
            raise Http404("Lookup value not provided.")

        lookup_str = str(lookup_value).strip()
        if lookup_str.isdigit():
            obj = get_object_or_404(queryset, id=int(lookup_str))
        else:
            obj = get_object_or_404(queryset, slug=lookup_str)

        self.check_object_permissions(self.request, obj)
        return obj


class CategoryViewSet(DualLookupMixin, viewsets.ModelViewSet):
    """
    API endpoint for supplement categories.
    Public: List/Retrieve active categories only.
    Admin: Full CRUD including inactive categories.
    Lookup supports both numeric ID and slug.
    """

    permission_classes = [IsAdminOrReadOnly]
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def _is_admin(self) -> bool:
        user = self.request.user
        return bool(user and user.is_authenticated and getattr(user, "is_admin_role", False))

    def get_queryset(self):
        if self._is_admin():
            # Admins see all categories, product_count reflects all products
            return Category.objects.annotate(
                product_count=Count("products")
            ).order_by("name")

        # Public users see only active categories, product_count reflects active products only
        return (
            Category.objects.filter(is_active=True)
            .annotate(
                product_count=Count("products", filter=Q(products__is_active=True))
            )
            .order_by("name")
        )


class ProductViewSet(DualLookupMixin, viewsets.ModelViewSet):
    """
    API endpoint for supplement products.
    Public: List/Retrieve active products from active categories.
    Admin: Full CRUD with draft/archived visibility.
    Supports search, category/brand/price filtering, ordering, and dual ID/slug lookup.
    """

    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "brand", "category__name"]
    ordering_fields = ["price", "created_at", "name", "stock_quantity"]
    ordering = ["-created_at"]

    def _is_admin(self) -> bool:
        user = self.request.user
        return bool(user and user.is_authenticated and getattr(user, "is_admin_role", False))

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return ProductWriteSerializer
        return ProductDetailSerializer

    def get_queryset(self):
        if self._is_admin():
            queryset = Product.objects.select_related("category")
            is_active_param = self.request.query_params.get("is_active")
            if is_active_param is not None:
                if is_active_param.lower() in ["true", "1"]:
                    queryset = queryset.filter(is_active=True)
                elif is_active_param.lower() in ["false", "0"]:
                    queryset = queryset.filter(is_active=False)
        else:
            # Public users: only active products in active categories
            queryset = Product.objects.select_related("category").filter(
                is_active=True,
                category__is_active=True,
            )

        # Filter by category (by ID or slug)
        category_param = self.request.query_params.get("category")
        if category_param:
            category_param = category_param.strip()
            if category_param.isdigit():
                queryset = queryset.filter(category_id=int(category_param))
            else:
                queryset = queryset.filter(category__slug=category_param)

        # Filter by brand
        brand_param = self.request.query_params.get("brand")
        if brand_param:
            queryset = queryset.filter(brand__iexact=brand_param.strip())

        # Filter by featured status
        featured_param = self.request.query_params.get("featured")
        if featured_param is not None:
            if featured_param.lower() in ["true", "1"]:
                queryset = queryset.filter(is_featured=True)
            elif featured_param.lower() in ["false", "0"]:
                queryset = queryset.filter(is_featured=False)

        # Filter by stock availability
        in_stock_param = self.request.query_params.get("in_stock")
        if in_stock_param is not None:
            if in_stock_param.lower() in ["true", "1"]:
                queryset = queryset.filter(stock_quantity__gt=0)
            elif in_stock_param.lower() in ["false", "0"]:
                queryset = queryset.filter(stock_quantity=0)

        # Filter by price range
        min_price = self.request.query_params.get("min_price")
        if min_price:
            try:
                queryset = queryset.filter(price__gte=Decimal(min_price))
            except (InvalidOperation, ValueError):
                pass

        max_price = self.request.query_params.get("max_price")
        if max_price:
            try:
                queryset = queryset.filter(price__lte=Decimal(max_price))
            except (InvalidOperation, ValueError):
                pass

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = ProductDetailSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output_serializer = ProductDetailSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)
